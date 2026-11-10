"""Opt-in, time-limited camera observation; never publishes control or acts on the car."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time

from openpilot.tools.clearance_shadow.onnx_observer import MODEL_SHA256

MODEL = Path('/data/truck-shadow/truck-best.onnx')
RUNTIME = Path('/data/truck-shadow/runtime')
RUN_DIR = Path('/dev/shm/truck-shadow')
ARM_DURATION_NS = 300 * 1_000_000_000


def requested(directory=RUN_DIR, now_ns=None):
  now_ns = time.monotonic_ns() if now_ns is None else now_ns
  try:
    path = Path(directory) / 'armed.json'
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 512:
      return False
    info = json.loads(path.read_text())
    expiry = info['expires_monotonic_ns']
    return (info['version'] == 1 and isinstance(expiry, int) and not isinstance(expiry, bool)
            and 0 < expiry - now_ns <= ARM_DURATION_NS)
  except (OSError, ValueError, TypeError, KeyError):
    return False


def check_model(path=MODEL):
  digest = hashlib.sha256()
  with Path(path).open('rb') as src:
    for block in iter(lambda: src.read(1024 * 1024), b''):
      digest.update(block)
  if digest.hexdigest() != MODEL_SHA256:
    raise ValueError('truck model checksum mismatch')
  return str(path)


def next_delay(wall_s, cpu_s):
  if not math.isfinite(wall_s) or not math.isfinite(cpu_s) or wall_s < 0 or cpu_s < 0:
    raise ValueError('negative duration')
  # At most 1 Hz, with long pauses after expensive work. Startup is not included.
  return max(.1, 1.0 - wall_s, 9.0 * cpu_s)


def wait_or_disarm(delay):
  end = time.monotonic() + delay
  while requested() and time.monotonic() < end:
    time.sleep(min(.2, max(0, end - time.monotonic())))


def healthy(params, sm):
  try:
    return (params.get_bool('IsOnroad') and not params.get_bool('IsOffroad')
            and not any(params.get_bool(k) for k in ('DoShutdown', 'DoReboot', 'DoUninstall'))
            and all(sm.seen[n] for n in ('deviceState', 'modelV2'))
            and sm.all_alive(['deviceState', 'modelV2'])
            and sm.all_valid(['deviceState', 'modelV2'])
            and bool(sm['deviceState'].started) and str(sm['deviceState'].thermalStatus) == 'green')
  except Exception:
    return False


def write_status(directory, record):
  directory = Path(directory)
  directory.mkdir(mode=0o700, parents=True, exist_ok=True)
  record = dict(record, updated_monotonic_ns=time.monotonic_ns(),
                control_eligible=False, applied_offset_m=0.0)
  temporary = directory / 'latest.tmp'
  temporary.write_text(json.dumps(record, allow_nan=False, separators=(',', ':')))
  temporary.replace(directory / 'latest.json')


def status_snapshot(directory=RUN_DIR, now_ns=None):
  now_ns = time.monotonic_ns() if now_ns is None else now_ns
  latest = None
  try:
    latest = json.loads((Path(directory) / 'latest.json').read_text())
  except (OSError, ValueError):
    pass
  age_s = None
  if isinstance(latest, dict) and isinstance(latest.get('updated_monotonic_ns'), int):
    timestamp = latest['updated_monotonic_ns']
    if 0 <= timestamp <= now_ns:
      age_s = (now_ns - timestamp) / 1e9
  armed = requested(directory, now_ns)
  fresh = bool(armed and age_s is not None and age_s <= 3 and latest.get('state') == 'observing')
  if isinstance(latest, dict) and not fresh:
    latest = dict(latest, detections=[])
  return {'armed': armed, 'latest_fresh': fresh, 'latest_age_s': age_s, 'latest': latest,
          'control_eligible': False, 'applied_offset_m': 0.0}


def configure_worker_scheduling():
  allowed = os.sched_getaffinity(0) & {0, 1, 2, 3}
  if not allowed:
    raise RuntimeError('no permitted low-priority CPU')
  for task in Path('/proc/self/task').iterdir():
    try:
      tid = int(task.name)
      os.sched_setaffinity(tid, allowed)
      os.sched_setscheduler(tid, os.SCHED_OTHER, os.sched_param(0))
      os.setpriority(os.PRIO_PROCESS, tid, 19)
    except ProcessLookupError:
      pass


def configure_worker_limits():
  import resource
  import signal

  soft, hard = resource.getrlimit(resource.RLIMIT_CPU)
  limit = 30
  if soft != resource.RLIM_INFINITY:
    limit = min(limit, soft)
  if hard != resource.RLIM_INFINITY:
    limit = min(limit, hard)
  hard_limit = limit + 1 if hard == resource.RLIM_INFINITY else min(hard, limit + 1)
  resource.setrlimit(resource.RLIMIT_CPU, (limit, hard_limit))
  signal.alarm(330)


def load_session(path=MODEL):
  import sys
  sys.path.insert(0, str(RUNTIME))
  import onnxruntime as ort

  path = check_model(path)
  options = ort.SessionOptions()
  options.intra_op_num_threads = 1
  options.inter_op_num_threads = 1
  options.add_session_config_entry('session.intra_op.allow_spinning', '0')
  session = ort.InferenceSession(path, sess_options=options, providers=['CPUExecutionProvider'])
  if (len(session.get_inputs()) != 1 or session.get_inputs()[0].name != 'images'
      or session.get_inputs()[0].shape != [1, 3, 640, 640]
      or len(session.get_outputs()) != 1 or session.get_outputs()[0].shape != [1, 14, 8400]):
    raise ValueError('unexpected model interface')
  return session, ort.__version__


def run():
  for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
  configure_worker_scheduling()
  configure_worker_limits()
  from msgq.visionipc import VisionIpcClient, VisionStreamType
  import openpilot.cereal.messaging as messaging
  from openpilot.common.params import Params
  from openpilot.common.swaglog import cloudlog
  from openpilot.selfdrive.modeld.signal_color_shadow import rgb_from_nv12
  from openpilot.tools.clearance_shadow.onnx_observer import decode_output, letterbox_rgb

  if not requested():
    return
  import fcntl
  with (RUN_DIR / 'worker.lock').open('a') as lock_file:
    try:
      fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
      return
    observe(VisionIpcClient, VisionStreamType, messaging, Params, cloudlog,
            rgb_from_nv12, decode_output, letterbox_rgb)


def observe(VisionIpcClient, VisionStreamType, messaging, Params, cloudlog,
            rgb_from_nv12, decode_output, letterbox_rgb):
  write_status(RUN_DIR, {'state': 'loading_model', 'pid': os.getpid()})
  session, runtime_version = load_session()
  params = Params()
  sm = messaging.SubMaster(['deviceState', 'modelV2'])
  client = VisionIpcClient('camerad', VisionStreamType.VISION_STREAM_ROAD, True)
  previous_id = None
  while requested():
    sm.update(100)
    if not healthy(params, sm):
      write_status(RUN_DIR, {'state': 'waiting_for_healthy_onroad'})
      time.sleep(.5)
      continue
    if not client.is_connected() and not client.connect(False):
      write_status(RUN_DIR, {'state': 'waiting_for_camera'})
      time.sleep(.5)
      continue
    frame = client.recv(timeout_ms=100)
    if frame is None:
      write_status(RUN_DIR, {'state': 'waiting_for_camera_frame'})
      time.sleep(.2)
      continue
    frame_id, eof = int(client.frame_id), int(client.timestamp_eof)
    if frame_id == previous_id:
      write_status(RUN_DIR, {'state': 'waiting_for_new_frame'})
      time.sleep(.2)
      continue
    previous_id = frame_id
    start, cpu_start = time.monotonic(), time.process_time()
    age_ms = (time.monotonic_ns() - eof) / 1e6
    if age_ms < 0 or age_ms > 300:
      write_status(RUN_DIR, {'state': 'stale_camera_frame'})
      time.sleep(.2)
      continue
    rgb = rgb_from_nv12(frame.data, frame.width, frame.height, frame.stride, frame.uv_offset)
    if int(frame.frame_id) != frame_id:
      write_status(RUN_DIR, {'state': 'camera_buffer_reused'})
      time.sleep(.2)
      continue
    image, transform = letterbox_rgb(rgb)
    boxes = decode_output(session.run(None, {'images': image})[0], transform)
    wall, cpu = time.monotonic() - start, time.process_time() - cpu_start
    sm.update(0)
    result_age = (time.monotonic_ns() - eof) / 1e6
    usable = requested() and healthy(params, sm) and 0 <= result_age <= 1500
    record = {'state': 'observing' if usable else 'stale_or_unhealthy', 'pid': os.getpid(), 'frame_id': frame_id,
              'timestamp_eof_ns': eof, 'input_age_ms': age_ms, 'result_age_ms': result_age,
              'work_ms': wall * 1000, 'cpu_ms': cpu * 1000, 'next_delay_s': next_delay(wall, cpu),
              'image_size': [int(frame.width), int(frame.height)], 'model_sha256': MODEL_SHA256,
              'runtime': runtime_version, 'detections': boxes if usable else [],
              'control_eligible': False, 'applied_offset_m': 0.0}
    write_status(RUN_DIR, record)
    cloudlog.event('truckShadowObservation', **record)
    wait_or_disarm(next_delay(wall, cpu))


def main():
  try:
    run()
  except Exception as error:
    from openpilot.common.swaglog import cloudlog
    cloudlog.exception('truck shadow observer disabled')
    try:
      write_status(RUN_DIR, {'state': 'error', 'error': str(error)[:200]})
    except Exception:
      pass


def arm_worker(gate, prepare, launch, directory=RUN_DIR, clock=time.monotonic,
               clock_ns=time.monotonic_ns, pause=time.sleep):
  """Arm only after a continuous offroad interval and a final post-setup check."""
  directory = Path(directory)
  if requested(directory, clock_ns()):
    raise RuntimeError('already armed; turn off before arming again')
  start = clock()
  stable = None
  while clock() - start < 25:
    now = clock()
    stable = (stable if stable is not None else now) if gate() else None
    if stable is not None and now - stable >= 15:
      break
    pause(.5)
  else:
    raise RuntimeError('offroad/ignition-off was not stable for 15 seconds')
  prepare()
  if not gate():
    raise RuntimeError('offroad/ignition-off no longer confirmed')
  directory.mkdir(mode=0o700, parents=True, exist_ok=True)
  (directory / 'latest.json').unlink(missing_ok=True)
  tmp = directory / 'armed.tmp'
  tmp.write_text(json.dumps({'version': 1, 'expires_monotonic_ns': clock_ns() + ARM_DURATION_NS}))
  tmp.replace(directory / 'armed.json')
  try:
    launch()
  except Exception:
    (directory / 'armed.json').unlink(missing_ok=True)
    raise


def cli():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('command', choices=('arm', 'off', 'status', 'worker'))
  args = parser.parse_args()
  directory = RUN_DIR
  if args.command == 'arm':
    import importlib.util
    import subprocess
    import sys
    from openpilot.cereal import log
    import openpilot.cereal.messaging as messaging
    from openpilot.common.params import Params
    from openpilot.tools.clearance_shadow.auto_capture import LiveOffroadGate

    sm = messaging.SubMaster(['deviceState', 'pandaStates'])
    gate = LiveOffroadGate(Params(), sm, log.PandaState.PandaType.unknown)

    def prepare():
      check_model()
      sys.path.insert(0, str(RUNTIME))
      if importlib.util.find_spec('onnxruntime') is None or importlib.util.find_spec('PIL') is None:
        raise RuntimeError('onnxruntime or Pillow runtime missing')

    def launch():
      subprocess.Popen([sys.executable, '-m', 'openpilot.tools.clearance_shadow.live_observer', 'worker'], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    arm_worker(gate, prepare, launch, directory)
  elif args.command == 'off':
    (directory / 'armed.json').unlink(missing_ok=True)
  elif args.command == 'worker':
    main()
    return
  print(json.dumps(status_snapshot(directory), ensure_ascii=False, indent=2))


if __name__ == '__main__':
  cli()
