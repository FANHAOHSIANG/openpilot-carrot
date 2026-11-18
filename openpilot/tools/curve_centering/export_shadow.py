"""Extract only shadow diagnostics from local swaglog or rlog; never upload logs."""
import argparse
import json
from pathlib import Path

FIELDS = {'event', 'mode', 'vehicle_output', 'sequence', 'generation', 'now_ns', 'observation_age_ns',
          'reasons', 'reason', 'actual_baseline_error', 'policy_delta_curvature', 'history_delta_curvature',
          'worker_wall_ns', 'worker_cpu_ns'}


def extract(record):
  if isinstance(record, str):
    record = json.loads(record)
  msg = record.get('msg')
  if not isinstance(msg, dict):
    return None
  msg = {k.split('$', 1)[0]: v for k, v in msg.items()}
  if msg.get('event') not in ('curve_centering_shadow', 'curve_centering_shadow_stopped'):
    return None
  # Omit outer context, host, process, timestamps, device/route identifiers and unknown fields.
  return {k: v for k, v in msg.items() if k in FIELDS}


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('inputs', type=Path, nargs='+')
  parser.add_argument('--format', choices=('swaglog', 'rlog'), default='swaglog')
  parser.add_argument('--output', type=Path, required=True)
  args = parser.parse_args()
  count = 0
  with args.output.open('x') as output:
    for path in args.inputs:
      if args.format == 'rlog':
        from openpilot.tools.lib.logreader import LogReader
        records = (str(m.logMessage) for m in LogReader(str(path)) if m.which() == 'logMessage')
      else:
        records = path.read_text().splitlines()
      for raw in records:
        result = extract(raw)
        if result is not None:
          output.write(json.dumps(result, allow_nan=False)+'\n')
          count += 1
  print(f'{count} shadow records exported')


if __name__ == '__main__':
  main()
