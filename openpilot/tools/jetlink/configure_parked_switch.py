"""Enable/disable the integrated parked switch while genuinely offroad."""
import argparse
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
FLAG = Path('/data/jetlink-parked-model-switch')
PARAMS = Path('/data/params/d')


def require_offroad(params=PARAMS):
  if (params / 'IsOffroad').read_bytes() != b'1' or (params / 'IsOnroad').read_bytes() != b'0':
    raise ValueError('Turn ignition off, keep the comma powered and wait for genuine offroad. Do not edit these Params.')


def configure(enabled, *, params=PARAMS, flag=FLAG, root=ROOT):
  require_offroad(params)
  if enabled:
    for name in ('daemon', 'mac', 'model', 'parked'):
      if not (root / f'openpilot/selfdrive/modeld/jetlink/{name}.py').is_file():
        raise ValueError('The integrated parked-switch source is missing.')
    subprocess.run([sys.executable, str(root / 'openpilot/selfdrive/modeld/tests/test_parked_switch.py')],
                   check=True, cwd=root)
  require_offroad(params)
  previous = flag.read_bytes() if flag.is_file() else None
  try:
    if enabled:
      flag.write_text('1\n')
    else:
      flag.unlink(missing_ok=True)
    require_offroad(params)
  except BaseException:
    if previous is None:
      flag.unlink(missing_ok=True)
    else:
      flag.write_bytes(previous)
    raise


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  action = parser.add_mutually_exclusive_group(required=True)
  action.add_argument('--enable', action='store_true')
  action.add_argument('--disable', action='store_true')
  action.add_argument('--status', action='store_true')
  args = parser.parse_args()
  if args.status:
    print('parked-switch enabled' if FLAG.is_file() else 'parked-switch disabled')
    return
  # Coordinate concurrent configuration calls; this does not replace runtime
  # CAN/control freshness and native-model handoff checks.
  import fcntl
  with Path('/data/jetlink-parked-switch.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    configure(args.enable)
  print('Parked-switch enabled.' if args.enable else 'Parked-switch disabled.')
  print('Remain offroad and reboot the comma. Vehicle operation remains unvalidated.')


if __name__ == '__main__':
  try:
    main()
  except (ValueError, OSError, subprocess.CalledProcessError) as error:
    print(f'Parked-switch configuration stopped: {error}', file=sys.stderr)
    sys.exit(1)
