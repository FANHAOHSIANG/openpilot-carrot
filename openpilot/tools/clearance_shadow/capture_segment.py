#!/usr/bin/env python3
"""Package a closed C4 road-camera segment for offline shadow replay.

The capture command runs only while IsOffroad is explicitly true. It reads
existing logger files and never publishes messages or changes vehicle settings.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import zipfile


SOURCE_FILES = ('rlog.zst', 'fcamera.hevc')
MANIFEST = 'manifest.json'
CHUNK = 4 * 1024 * 1024
FREE_RESERVE = 1024 * 1024 * 1024
SEGMENT_PATTERN = re.compile(r'.+--[0-9]+$')


def assert_offroad_and_closed(segment, offroad):
  if not offroad():
    raise RuntimeError('IsOffroad is not true; stop and try again after the device goes offroad')
  if any(p.name.endswith('.lock') for p in segment.iterdir()):
    raise RuntimeError('segment contains a logger lock; it may still be recording')


def source_stat(path):
  info = path.lstat()
  if not stat.S_ISREG(info.st_mode) or info.st_size <= 0:
    raise ValueError(f'{path.name} must be a non-empty regular file')
  return info


def same_file(a, b):
  return (a.st_dev, a.st_ino, a.st_size, a.st_mtime_ns) == (b.st_dev, b.st_ino, b.st_size, b.st_mtime_ns)


def list_segments(root, limit=15):
  if limit < 1 or limit > 100:
    raise ValueError('limit must be between 1 and 100')
  candidates = []
  for segment in root.iterdir():
    if segment.is_symlink() or not segment.is_dir() or not SEGMENT_PATTERN.fullmatch(segment.name):
      continue
    try:
      sizes = {name: source_stat(segment / name).st_size for name in SOURCE_FILES}
      locked = any(p.name.endswith('.lock') for p in segment.iterdir())
      candidates.append((segment.stat().st_mtime_ns, {'segment': segment.name, 'locked': locked, 'bytes': sizes}))
    except (FileNotFoundError, PermissionError, ValueError):
      continue
  return [item for _, item in sorted(candidates, key=lambda x: x[0], reverse=True)[:limit]]


def pack_segment(root, segment_name, output, offroad):
  root, output = Path(root).resolve(), Path(output)
  if not SEGMENT_PATTERN.fullmatch(segment_name) or Path(segment_name).name != segment_name:
    raise ValueError('choose one segment name shown by list')
  segment = root / segment_name
  if segment.is_symlink() or not segment.is_dir() or segment.resolve().parent != root:
    raise ValueError('segment must be a real directory directly under the logger root')
  if not output.parent.is_dir():
    raise ValueError('output parent directory does not exist')
  if output.resolve().is_relative_to(segment.resolve()):
    raise ValueError('output must not be inside the source segment')
  if output.exists() or output.is_symlink():
    raise FileExistsError('output already exists')
  assert_offroad_and_closed(segment, offroad)
  initial = {name: source_stat(segment / name) for name in SOURCE_FILES}
  total = sum(info.st_size for info in initial.values())
  if shutil.disk_usage(output.parent).free < total + FREE_RESERVE:
    raise OSError('not enough free space to keep a 1 GiB reserve')
  manifest = {'schema': 1, 'segment': segment_name, 'files': {},
              'scope': 'recorded_data_for_offline_shadow_replay', 'control_eligible': False}
  created = False
  try:
    with zipfile.ZipFile(output, mode='x', compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
      created = True
      for name in SOURCE_FILES:
        path = segment / name
        digest = hashlib.sha256()
        count = 0
        assert_offroad_and_closed(segment, offroad)
        # O_NOFOLLOW prevents replacing a checked input with a symbolic link.
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(fd, 'rb') as source, archive.open(name, mode='w', force_zip64=True) as target:
          if not same_file(initial[name], os.fstat(source.fileno())):
            raise RuntimeError(f'{name} changed before copying')
          while True:
            assert_offroad_and_closed(segment, offroad)
            block = source.read(CHUNK)
            if not block:
              break
            target.write(block)
            digest.update(block)
            count += len(block)
          if not same_file(initial[name], os.fstat(source.fileno())) or count != initial[name].st_size:
            raise RuntimeError(f'{name} changed while copying')
        if not same_file(initial[name], source_stat(path)):
          raise RuntimeError(f'{name} was replaced while copying')
        manifest['files'][name] = {'size_bytes': count, 'sha256': digest.hexdigest()}
      assert_offroad_and_closed(segment, offroad)
      archive.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    assert_offroad_and_closed(segment, offroad)
  except BaseException:
    if created:
      output.unlink(missing_ok=True)
    raise
  return manifest


def verify_archive(path):
  with zipfile.ZipFile(path) as archive:
    names = archive.namelist()
    if len(names) != 3 or set(names) != {*SOURCE_FILES, MANIFEST}:
      raise ValueError('unexpected, missing, or duplicate archive entries')
    if archive.getinfo(MANIFEST).file_size > 64 * 1024:
      raise ValueError('manifest too large')
    manifest = json.loads(archive.read(MANIFEST))
    if manifest.get('schema') != 1 or set(manifest.get('files', {})) != set(SOURCE_FILES):
      raise ValueError('invalid manifest')
    for name in SOURCE_FILES:
      entry = manifest['files'][name]
      if archive.getinfo(name).file_size != entry.get('size_bytes'):
        raise ValueError(f'{name} size mismatch')
      digest = hashlib.sha256()
      with archive.open(name) as source:
        for block in iter(lambda: source.read(CHUNK), b''):
          digest.update(block)
      if digest.hexdigest() != entry.get('sha256'):
        raise ValueError(f'{name} SHA-256 mismatch')
  return manifest


def device_offroad():
  # Missing IsOffroad returns false, so startup/unknown state fails closed.
  from openpilot.common.params import Params
  return Params().get_bool('IsOffroad')


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  sub = parser.add_subparsers(dest='command', required=True)
  listing = sub.add_parser('list', help='show recent segments with both source files')
  listing.add_argument('--limit', type=int, default=15)
  pack = sub.add_parser('pack', help='copy a closed segment while offroad')
  pack.add_argument('--segment', required=True, help='exact segment name returned by list')
  pack.add_argument('--output', type=Path, required=True, help='new .zip path outside the source segment')
  verify = sub.add_parser('verify', help='verify an archive without extracting it')
  verify.add_argument('archive', type=Path)
  args = parser.parse_args()
  if args.command == 'verify':
    result = verify_archive(args.archive)
  else:
    from openpilot.system.hardware.hw import Paths
    root = Path(Paths.log_root())
    if args.command == 'list':
      result = {'logger_root': str(root), 'segments': list_segments(root, args.limit)}
    else:
      result = pack_segment(root, args.segment, args.output, device_offroad)
  print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
  main()
