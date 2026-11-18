"""Summarize synthetic full-process timings without treating percentiles as deadlines."""
import argparse
from collections import Counter
import json
from pathlib import Path

from .process_bench import phase


def distribution(values):
  values = sorted(values)
  if not values:
    return None
  def percentile(p):
    return values[min(len(values)-1, round((len(values)-1)*p))]/1e6
  return {'count': len(values), 'median_ms': percentile(.5), 'p95_ms': percentile(.95),
          'p99_ms': percentile(.99), 'max_ms': values[-1]/1e6,
          'over_10ms': sum(v > 10_000_000 for v in values), 'over_15ms': sum(v > 15_000_000 for v in values)}


def summarize(directory):
  data = json.loads((directory/'child.json').read_text())
  receiver = json.loads((directory/'receiver.json').read_text())
  received = {r['message_ns']: r['received_ns'] for r in receiver['received']}
  pubs = data['publications']
  intervals = {b['message_ns']: b['message_ns']-a['message_ns'] for a, b in zip(pubs, pubs[1:], strict=False)}
  rows = []
  for name in dict.fromkeys(phase(p['at']) for p in pubs):
    ps = [p for p in pubs if phase(p['at']) == name]
    cs = [c for c in data['captures'] if phase(c['at']) == name]
    ws = [w for w in data['worker'] if phase(w['at']) == name]
    rows.append({'phase': name, 'publications': len(ps), 'lat_active': sum(p['lat_active'] for p in ps),
                 'publication_interval': distribution([intervals[p['message_ns']] for p in ps if p['message_ns'] in intervals]),
                 'state_wall': distribution([p['state_wall_ns'] for p in ps]),
                 'capture_wall': distribution([c['wall_ns'] for c in cs]),
                 'capture_cpu': distribution([c['cpu_ns'] for c in cs]),
                 'worker_wall': distribution([w['wall_ns'] for w in ws]),
                 'worker_cpu': distribution([w['cpu_ns'] for w in ws]),
                 'observation_age': distribution([w['age_ns'] for w in ws if w.get('age_ns') is not None]),
                 'input_to_publish': distribution([p['publish_end_ns']-p['input_ns'] for p in ps]),
                 'input_to_receiver': distribution([received[p['message_ns']]-p['input_ns'] for p in ps if p['message_ns'] in received]),
                 'unreceived': sum(p['message_ns'] not in received for p in ps),
                 'max_dropped': max((p['dropped'] for p in ps), default=0),
                 'monitor_failed': sum(p['monitor_failed'] for p in ps),
                 'thread_alive': sum(p['thread_alive'] for p in ps),
                 'monitor_present': sum(p.get('monitor_present', p['thread_alive']) for p in ps),
                 'nonzero_policy_steps': sum(w['policy_delta'] is not None and w['policy_delta'] != 0 for w in ws),
                 'worker_reasons': dict(Counter(reason for w in ws for reason in w['reasons']))})
  return {'trial': directory.name, 'backend': data.get('backend', 'legacy_thread'),
          'load_location': data.get('load_location', 'control'),
          'partial_worker_reports': data.get('partial_worker_reports', 0), 'scope': 'desktop_synthetic_mock_car_full_controlsd_with_measurement_wrappers',
          'deployment_approved': False, 'receiver_poll_s': .01, 'worker_stopped': data['worker_stopped'],
          'worker_failures': data.get('worker_failures'), 'events': data.get('events', []),
          'input_send_intervals': distribution([b-a for a,b in zip(receiver['sent'],receiver['sent'][1:], strict=False)]),
          'phases': rows}


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('directories', type=Path, nargs='+')
  parser.add_argument('--output', type=Path, required=True)
  args = parser.parse_args()
  result = [summarize(d) for d in args.directories]
  with args.output.open('x') as f:
    json.dump(result, f, indent=2, allow_nan=False)
  print(json.dumps(result, indent=2))


if __name__ == '__main__':
  main()
