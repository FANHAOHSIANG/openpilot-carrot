"""Replay local rlogs into a read-only centering report. No URL downloads."""

import argparse
import bz2
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from statistics import median

from .observer import Config, Observer, from_event

PARAM_KEYS = {'PathOffset', 'AdjustLaneOffset', 'LatMpcInputOffset', 'UseLaneLineSpeed', 'LateralTorqueCustom', 'SteerActuatorDelay'}


def read_records(path):
  # Full cereal schema is essential; the opendbc CAN-only schema loses services.
  from openpilot.cereal import log
  import zstandard

  raw = Path(path).read_bytes()
  if raw[:4] == b'\x28\xb5\x2f\xfd':
    raw = zstandard.ZstdDecompressor().stream_reader(raw).read()
  elif raw[:3] == b'BZh':
    raw = bz2.decompress(raw)
  counts, records, metadata = Counter(), [], {}
  # Intentionally strict: truncated/corrupt files are reported, never silently accepted.
  for event in log.Event.read_multiple_bytes(raw):
    counts[event.which()] += 1
    if event.which() == 'initData':
      initial = event.initData
      metadata['git_commit'] = str(initial.gitCommit)
      metadata['git_branch'] = str(initial.gitBranch)
      metadata['initial_parameters_raw'] = {
        str(e.key): bytes(e.value).decode('utf-8', errors='replace') for e in initial.params.entries if str(e.key) in PARAM_KEYS
      }
      metadata['parameter_scope'] = 'start_snapshot_only_not_verified_unchanged_during_drive'
    elif event.which() == 'carParams':
      metadata['car_fingerprint'] = str(event.carParams.carFingerprint)
    record = from_event(event)
    if record is not None:
      records.append(record)
  return sorted(records, key=lambda r: r['mono_ns']), dict(counts), metadata


def summarize(rows):
  eligible = [r for r in rows if r['eligible']]
  reasons = Counter(reason for r in rows for reason in r['reasons'])
  groups = {}
  for direction in ('left', 'right', 'straight'):
    selected = [r for r in eligible if r['direction'] == direction]
    values = sorted(abs(r['geometry']['request_bias_m']) for r in selected)
    groups[direction] = {
      'frames': len(selected),
      'median_abs_request_bias_m': median(values) if values else None,
      'p95_abs_request_bias_m': values[min(len(values) - 1, int(len(values) * 0.95))] if values else None,
    }
  return {
    'frames': len(rows),
    'eligible_frames': len(eligible),
    'excluded_frames': len(rows) - len(eligible),
    'reason_counts': dict(reasons),
    'finding_counts': dict(Counter(f for r in eligible for f in r['findings'])),
    'by_direction': groups,
  }


def episodes(rows, threshold=0.2, min_duration=0.5):
  """Sustained requested-path deviations, split at exclusions, side changes and gaps."""
  result, run = [], []

  def flush():
    if run and run[-1]['t'] - run[0]['t'] >= min_duration:
      result.append(
        {
          'source': run[0]['source'],
          'start_s': run[0]['relative_s'],
          'end_s': run[-1]['relative_s'],
          'direction': run[0]['direction'],
          'frames': len(run),
          'median_request_bias_m': median(r['geometry']['request_bias_m'] for r in run),
          'max_abs_request_bias_m': max(abs(r['geometry']['request_bias_m']) for r in run),
          'findings': sorted({f for r in run for f in r['findings']}),
          'meaning': 'model_geometry_review_candidate_not_confirmed_fault',
        }
      )
    run.clear()

  for r in rows:
    if not r['eligible'] or abs(r['geometry']['request_bias_m']) <= threshold:
      flush()
      continue
    if run and (
      r['source'] != run[-1]['source']
      or r['direction'] != run[-1]['direction']
      or not 0 < r['t'] - run[-1]['t'] <= 0.2
      or r['geometry']['request_bias_m'] * run[-1]['geometry']['request_bias_m'] < 0
    ):
      flush()
    run.append(r)
  flush()
  return result


def replay(paths, config=None):
  config = config or Config()
  rows, sources, seen = [], [], set()
  for path in paths:
    p = Path(path)
    source = {'name': p.name}
    sources.append(source)
    try:
      digest = hashlib.sha256(p.read_bytes()).hexdigest()
      source['sha256'] = digest
      if digest in seen:
        source['status'] = 'duplicate_skipped'
        continue
      seen.add(digest)
      records, counts, metadata = read_records(p)
      source['service_counts'] = counts
      source['metadata'] = metadata
      observer = Observer(config)  # Each file begins a separate observation interval.
      start = next((r['t'] for r in records if r['kind'] == 'modelV2'), None)
      source_rows = []
      for record in records:
        row = observer.feed(record)
        if row is not None:
          row['source'] = p.name
          row['relative_s'] = row['t'] - start if start is not None else None
          source_rows.append(row)
      rows.extend(source_rows)
      source['status'] = 'ok' if source_rows else 'no_lateral_plans'
      source['summary'] = summarize(source_rows)
    except Exception as exc:
      # Corruption is visible per input; no partial-file claims or private paths in reports.
      source.update(status='error', error_type=type(exc).__name__, error='Cannot fully decode this input with the current schema.')
  return {
    'schema_version': 1,
    'mode': 'observe_only',
    'config': asdict(config),
    'sources': sources,
    'summary': summarize(rows),
    'episodes': episodes(rows, config.bias_threshold_m),
    'rows': rows,
    'limits': [
      'Camera/model estimates are not independently measured road geometry.',
      'No actuator, planner, Params or CAN changes. No trained driving model.',
      'Vehicle center/clearance requires explicit calibration and width.',
      'Replay is open-loop, not proof of improved vehicle behavior.',
      'Each file resets temporal context; incomplete files are rejected in full.',
    ],
  }


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('logs', nargs='+', help='Local uncompressed, bz2 or zstd rlogs (no URLs)')
  parser.add_argument('--output', required=True, type=Path, help='Output directory')
  parser.add_argument('--vehicle-center-y', type=float, help='Measured vehicle center y relative to model origin, right positive (m)')
  parser.add_argument('--vehicle-width', type=float, help='Measured vehicle width (m)')
  args = parser.parse_args()
  report = replay(args.logs, Config(vehicle_center_y_m=args.vehicle_center_y, vehicle_width_m=args.vehicle_width))
  args.output.mkdir(parents=True, exist_ok=True)
  (args.output / 'centering.json').write_text(json.dumps(report, ensure_ascii=False, allow_nan=False), encoding='utf-8')
  from .report import write_report

  write_report(args.output / 'centering.html', report)
  print(
    json.dumps(
      {
        'summary': report['summary'],
        'sources': [{k: v for k, v in s.items() if k != 'service_counts'} for s in report['sources']],
        'episodes': len(report['episodes']),
        'output': str(args.output),
      },
      ensure_ascii=False,
    )
  )
  return 2 if any(s['status'] == 'error' for s in report['sources']) else 0


if __name__ == '__main__':
  raise SystemExit(main())
