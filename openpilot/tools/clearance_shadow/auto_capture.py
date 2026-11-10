#!/usr/bin/env python3
"""Archive recent closed road-camera segments after a confirmed offroad transition.

This worker is started only offroad on the truck research branch. It copies
existing local recordings and never changes vehicle parameters or publishes
messages. Complete archives are installed atomically; interrupted temporary
files are discarded on a later offroad start.
"""
from contextlib import contextmanager
from datetime import UTC, datetime
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import time
import uuid
import zipfile

from openpilot.tools.clearance_shadow.capture_segment import MANIFEST, SOURCE_FILES, pack_segment, source_stat


ROUTE_RE = re.compile(r'^[0-9a-f]{8}--[0-9a-f]{10}$')
SEGMENT_RE = re.compile(r'^([0-9a-f]{8}--[0-9a-f]{10})--([0-9]+)$')
TEMP_RE = re.compile(r'^\.truck-auto-[0-9a-f]{8}--[0-9a-f]{10}--[0-9]+\.[0-9a-f]{32}\.part$')
MAX_ARCHIVE_BYTES = 5 * 1024 ** 3
MIN_FREE_BYTES = 6 * 1024 ** 3
FREE_MARGIN_BYTES = 256 * 1024 ** 2
ZIP_OVERHEAD_BYTES = 1024 ** 2
MAX_PENDING_ROUTES = 64
MAX_COMPLETED_ROUTES = 128
STABLE_OFFROAD_SECONDS = 15.0
RETRY_SECONDS = 30.0


def sync_directory(directory):
  fd = os.open(directory, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
  try:
    os.fsync(fd)
  finally:
    os.close(fd)


def write_json_atomic(path, obj):
  tmp = path.parent / f'.{path.name}.{uuid.uuid4().hex}.tmp'
  try:
    with open(tmp, 'x', encoding='utf-8') as target:
      json.dump(obj, target, ensure_ascii=False, indent=2)
      target.write('\n')
      target.flush()
      os.fsync(target.fileno())
    os.replace(tmp, path)
    sync_directory(path.parent)
  finally:
    tmp.unlink(missing_ok=True)


def load_state(path):
  if not path.exists():
    return {'version': 1, 'pending_routes': [], 'completed_routes': []}
  if path.is_symlink():
    raise ValueError('state file must not be a symlink')
  with open(path, encoding='utf-8') as source:
    state = json.load(source)
  if (not isinstance(state, dict) or state.get('version') != 1
      or not isinstance(state.get('pending_routes'), list) or not isinstance(state.get('completed_routes'), list)
      or len(state['pending_routes']) > MAX_PENDING_ROUTES or len(state['completed_routes']) > MAX_COMPLETED_ROUTES
      or not all(isinstance(x, str) and ROUTE_RE.fullmatch(x) for x in state['pending_routes'] + state['completed_routes'])
      or len(set(state['pending_routes'])) != len(state['pending_routes'])
      or len(set(state['completed_routes'])) != len(state['completed_routes'])
      or set(state['pending_routes']) & set(state['completed_routes'])):
    raise ValueError('invalid automatic archive state; original file retained')
  return state


@contextmanager
def worker_lock(directory):
  lock = directory / '.truck-auto.lock'
  fd = os.open(lock, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
  with os.fdopen(fd, 'a+') as holder:
    fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
      yield
    finally:
      fcntl.flock(holder, fcntl.LOCK_UN)


def clean_interrupted_parts(directory, offroad):
  if not offroad():
    raise RuntimeError('offroad state not confirmed')
  for path in directory.iterdir():
    if TEMP_RE.fullmatch(path.name) and not path.is_symlink() and path.is_file():
      if not offroad():
        raise RuntimeError('offroad state lost')
      path.unlink()


def list_routes(root):
  routes = {}
  for path in root.iterdir():
    match = SEGMENT_RE.fullmatch(path.name)
    if not match or path.is_symlink():
      continue
    try:
      if path.is_dir():
        routes.setdefault(match.group(1), []).append((int(match.group(2)), path, path.stat().st_mtime_ns))
    except FileNotFoundError:
      continue
  for segments in routes.values():
    segments.sort(key=lambda entry: entry[0], reverse=True)
  return routes


def select_route(routes, current_route):
  if isinstance(current_route, bytes):
    current_route = current_route.decode('utf-8', errors='replace')
  if isinstance(current_route, str) and ROUTE_RE.fullmatch(current_route) and current_route in routes:
    return current_route
  if not routes:
    return None
  # CurrentRoute is cleared on manager restart; use the most recently modified
  # remaining route only as a fallback, not all historical drives.
  return max(routes, key=lambda route: max(row[2] for row in routes[route]))


def archive_usage(directory):
  total = 0
  for path in directory.iterdir():
    if path.name.endswith('.zip') and SEGMENT_RE.fullmatch(path.name[:-4]) and not path.is_symlink():
      try:
        if path.is_file():
          total += path.stat().st_size
      except FileNotFoundError:
        pass
  return total


def space_reason(directory, next_bytes, quota_bytes=MAX_ARCHIVE_BYTES):
  if archive_usage(directory) + next_bytes > quota_bytes:
    return 'archive_quota'
  usage = shutil.disk_usage(directory)
  # The stock deleter begins below 5 GiB OR below 30% free. Keep an extra
  # margin so this copy does not intentionally cause it to delete route data.
  reserve = max(MIN_FREE_BYTES, (usage.total * 30 + 99) // 100 + FREE_MARGIN_BYTES)
  if usage.free - next_bytes < reserve:
    return 'free_space_reserve'
  return None


def inspect_archive(path, segment_name):
  """Check the completed archive structure; full hash verification is separate."""
  if path.is_symlink() or not path.is_file():
    return False
  try:
    with zipfile.ZipFile(path) as archive:
      names = archive.namelist()
      if len(names) != 3 or set(names) != {*SOURCE_FILES, MANIFEST} or archive.getinfo(MANIFEST).file_size > 65536:
        return False
      info = json.loads(archive.read(MANIFEST))
      if info.get('schema') != 1 or info.get('segment') != segment_name or set(info.get('files', {})) != set(SOURCE_FILES):
        return False
      return all(archive.getinfo(name).file_size == info['files'][name]['size_bytes'] for name in SOURCE_FILES)
  except (AttributeError, OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile):
    return False


def publish_segment(root, segment, destination, offroad, quota_bytes=MAX_ARCHIVE_BYTES):
  final = destination / (segment.name + '.zip')
  if final.exists() or final.is_symlink():
    if inspect_archive(final, segment.name):
      return 'already_archived'
    raise ValueError('existing archive is invalid; retained without overwrite')
  expected = sum(source_stat(segment / name).st_size for name in SOURCE_FILES) + ZIP_OVERHEAD_BYTES
  reason = space_reason(destination, expected, quota_bytes)
  if reason:
    raise OSError(reason)
  tmp = destination / f'.truck-auto-{segment.name}.{uuid.uuid4().hex}.part'

  def guarded_copy():
    if not offroad():
      return False
    usage = shutil.disk_usage(destination)
    reserve = max(MIN_FREE_BYTES, (usage.total * 30 + 99) // 100 + FREE_MARGIN_BYTES)
    if usage.free < reserve:
      raise OSError('free_space_reserve')
    return True

  try:
    pack_segment(root, segment.name, tmp, guarded_copy)
    if not guarded_copy():
      raise RuntimeError('offroad state lost')
    with open(tmp, 'rb') as source:
      os.fsync(source.fileno())
    if not guarded_copy():
      raise RuntimeError('offroad state lost')
    # Hard-link creation is atomic and never replaces a pre-existing archive.
    os.link(tmp, final, follow_symlinks=False)
    sync_directory(destination)
    return 'archived'
  finally:
    tmp.unlink(missing_ok=True)


def write_status(destination, status):
  status = dict(status, updated_utc=datetime.now(UTC).isoformat(), version=1)
  write_json_atomic(destination / 'status.json', status)


def process_once(root, destination, state, current_route, offroad, quota_bytes=MAX_ARCHIVE_BYTES,
                 road_camera_setting=None):
  """Schedule the current/most-recent trip and retry durable pending trips."""
  if not offroad():
    return {'state': 'offroad_not_confirmed'}
  routes = list_routes(root)
  latest = select_route(routes, current_route)
  if latest and latest not in state['pending_routes'] and latest not in state['completed_routes']:
    if len(state['pending_routes']) >= MAX_PENDING_ROUTES:
      status = {'state': 'pending_queue_full', 'latest_route': latest}
      write_status(destination, status)
      return status
    state['pending_routes'].append(latest)
    write_json_atomic(destination / 'state.json', state)

  saved, blocked = [], []
  for route in list(state['pending_routes']):
    segments = routes.get(route, [])
    if not segments:
      blocked.append({'route': route, 'reason': 'source_missing'})
      continue
    route_blocked = False
    for _, segment, _ in segments:
      if not offroad():
        return {'state': 'offroad_not_confirmed'}
      try:
        if any(p.name.endswith('.lock') for p in segment.iterdir()):
          blocked.append({'segment': segment.name, 'reason': 'recording_locked'})
          route_blocked = True
          continue
        missing = [name for name in SOURCE_FILES if not (segment / name).is_file()]
        if missing:
          blocked.append({'segment': segment.name, 'reason': 'missing_source', 'files': missing})
          route_blocked = True
          continue
        result = publish_segment(root, segment, destination, offroad, quota_bytes)
        if result == 'archived':
          saved.append(segment.name + '.zip')
      except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as error:
        if not offroad():
          return {'state': 'offroad_not_confirmed'}
        blocked.append({'segment': segment.name, 'reason': str(error)})
        route_blocked = True
    if not route_blocked:
      state['pending_routes'].remove(route)
      state['completed_routes'].append(route)
      state['completed_routes'] = state['completed_routes'][-MAX_COMPLETED_ROUTES:]
      write_json_atomic(destination / 'state.json', state)

  latest_files = [segment.name + '.zip' for _, segment, _ in routes.get(latest, [])
                  if (destination / (segment.name + '.zip')).is_file()]
  status = {'state': 'blocked' if blocked else 'ready' if latest else 'no_recordings', 'latest_route': latest,
            'pending_routes': list(state['pending_routes']), 'saved_this_pass': saved,
            'latest_route_archives': latest_files, 'record_road_cam_current': road_camera_setting,
            'blocked': blocked, 'archive_bytes': archive_usage(destination),
            'archive_quota_bytes': quota_bytes}
  write_status(destination, status)
  return status


class LiveOffroadGate:
  """Require fresh device/panda messages, ignition off, and manager agreement."""
  def __init__(self, params, sm, unknown_panda):
    self.params, self.sm, self.unknown_panda = params, sm, unknown_panda

  def __call__(self):
    try:
      self.sm.update(0)
      if (not self.params.get_bool('IsOffroad') or self.params.get_bool('IsOnroad')
          or any(self.params.get_bool(k) for k in ('DoShutdown', 'DoReboot', 'DoUninstall'))
          or not all(self.sm.seen[name] for name in ('deviceState', 'pandaStates'))
          or not self.sm.all_alive(['deviceState', 'pandaStates'])
          or not self.sm.all_valid(['deviceState', 'pandaStates']) or self.sm['deviceState'].started
          or str(self.sm['deviceState'].thermalStatus) not in ('green', 'yellow')):
        return False
      pandas = [p for p in self.sm['pandaStates'] if p.pandaType != self.unknown_panda]
      return bool(pandas) and not any(p.ignitionLine or p.ignitionCan for p in pandas)
    except Exception:
      return False


def wait_for_stable_offroad(gate, seconds=STABLE_OFFROAD_SECONDS, clock=time.monotonic, pause=time.sleep):
  since = None
  while True:
    now = clock()
    if gate():
      since = now if since is None else since
      if now - since >= seconds:
        return
    else:
      since = None
    pause(0.5)


def main():
  from openpilot.cereal import log
  import openpilot.cereal.messaging as messaging
  from openpilot.common.params import Params
  from openpilot.common.swaglog import cloudlog
  from openpilot.system.hardware.hw import Paths

  try:
    os.nice(10)
  except OSError:
    pass
  params = Params()
  sm = messaging.SubMaster(['deviceState', 'pandaStates'])
  gate = LiveOffroadGate(params, sm, log.PandaState.PandaType.unknown)
  root = Path(Paths.log_root())
  destination = root.parent / 'truck-shadow-auto'
  while True:
    wait_for_stable_offroad(gate)
    if not gate():
      return
    try:
      destination.mkdir(mode=0o700, parents=False, exist_ok=True)
      if destination.is_symlink() or not destination.is_dir():
        raise ValueError('automatic archive folder must be a real directory')
      with worker_lock(destination):
        state = load_state(destination / 'state.json')
        clean_interrupted_parts(destination, gate)
        while gate():
          try:
            process_once(root, destination, state, params.get('CurrentRoute'), gate,
                         road_camera_setting=params.get_int('RecordRoadCam'))
          except Exception:
            cloudlog.exception('truck shadow automatic archive failed')
          for _ in range(int(RETRY_SECONDS)):
            time.sleep(1)
            if not gate():
              return
    except Exception:
      cloudlog.exception('truck shadow automatic archive startup failed')
      for _ in range(int(RETRY_SECONDS)):
        time.sleep(1)
        if not gate():
          return


if __name__ == '__main__':
  main()
