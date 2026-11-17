"""Local-only per-control audit with exact consumed-model timestamp matching.

carState/liveParameters have no consumed-input IDs here: nearest preceding
samples are explicitly approximate. No dynamics or new control policy implied.
"""
import argparse
import bz2
from collections import Counter, deque
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from .model_baseline import SOURCE_COMMIT, model_step

SERVICES = {'modelV2', 'carState', 'liveParameters', 'controlsState', 'carControl', 'carrotMan'}


def audit(records):
  history = {k: deque(maxlen=256) for k in SERVICES}
  rows = []
  previous = None
  for record in sorted(records, key=lambda r: r['ns']):
    k, ns, d = record['kind'], record['ns'], record['data']
    if k != 'carControl':
      history[k].append(record)
      continue
    reasons = []
    ctl = history['controlsState'][-1] if history['controlsState'] else None
    row = {'ns': ns, 'active': d['latActive'], 'command': d['actuators']['curvature'],
           'torque': d['actuators']['torque'], 'reasons': reasons,
           'input_scope': 'model_exact_id_other_inputs_preceding_estimates'}
    if ctl is None or not 0 <= ns - ctl['ns'] <= 5_000_000:
      reasons.append('unpaired_controls_state')
    elif ctl['data']['desiredCurvature'] != row['command']:
      reasons.append('paired_command_mismatch')
    else:
      model_ns = ctl['data']['lateralPlanMonoTime']
      model = next((m for m in reversed(history['modelV2']) if m['ns'] == model_ns), None)
      row.update(model_ns=model_ns, feedback=ctl['data']['curvature'], lane_mode=ctl['data']['activeLaneLine'])
      if model is None or not 0 <= ctl['ns'] - model_ns <= 200_000_000:
        reasons.append('model_missing_or_stale')
      else:
        row.update(model_action=model['data']['action']['desiredCurvature'], model_age_ms=(ctl['ns']-model_ns)/1e6)
      states = {}
      for service, max_age in [('carState', 30_000_000), ('liveParameters', 200_000_000)]:
        state = next((s for s in reversed(history[service]) if s['ns'] <= ctl['ns']), None)
        if state is None or ctl['ns']-state['ns'] > max_age:
          reasons.append(service+'_missing_or_stale')
        else:
          states[service] = state
          row[service+'_age_ms'] = (ctl['ns']-state['ns'])/1e6
      relevant = [record, ctl, model, *states.values()]
      if any(s is not None and not s['valid'] for s in relevant):
        reasons.append('invalid_message')
      if row['lane_mode']:
        reasons.append('lane_baseline_pending')
      if previous is None or not 5_000_000 <= ns-previous['ns'] <= 15_000_000:
        reasons.append('control_gap_or_initial')
      elif d['latActive'] and not previous['data']['latActive']:
        reasons.append('engagement_initial_state_unknown')
      cs = states.get('carState', {}).get('data', {})
      row.update(speed_kph=cs.get('vEgo', 0)*3.6 if cs else None,
                 driver_pressed=cs.get('steeringPressed'), gas_pressed=cs.get('gasPressed'), brake_pressed=cs.get('brakePressed'))
      carrot = next((s for s in reversed(history['carrotMan']) if s['ns'] <= ctl['ns']), None)
      if carrot and ctl['ns']-carrot['ns'] <= 500_000_000:
        row['navigation'] = {key:carrot['data'].get(key) for key in ('atcType', 'desiredSource', 'desiredSpeed', 'vTurnSpeed')}
      if not reasons:
        try:
          result = model_step(speed=cs['vEgo'], previous=previous['data']['actuators']['curvature'],
                              action=row['model_action'], feedback=row['feedback'], roll=states['liveParameters']['data']['roll'],
                              active=d['latActive'], lateral_started=True)
          row['baseline'] = asdict(result)
          row['error'] = result.curvature-row['command']
        except (ValueError, KeyError) as exc:
          reasons.append('invalid_baseline_input:'+str(exc))
    rows.append(row)
    previous = record
  return rows


def read_local(path):
  from openpilot.cereal import log
  import zstandard
  raw = Path(path).read_bytes()
  digest = hashlib.sha256(raw).hexdigest()
  if raw[:4] == b'\x28\xb5\x2f\xfd':
    raw = zstandard.ZstdDecompressor().stream_reader(raw).read()
  elif raw[:3] == b'BZh':
    raw = bz2.decompress(raw)
  records = []
  fingerprint = commit = None
  for e in log.Event.read_multiple_bytes(raw):
    k = e.which()
    if k == 'carParams':
      fingerprint = str(e.carParams.carFingerprint)
    elif k == 'initData':
      commit = str(e.initData.gitCommit)
    if k in SERVICES:
      records.append({'kind':k, 'ns':int(e.logMonoTime), 'valid':bool(e.valid), 'data':e.to_dict()[k]})
  if fingerprint != 'HYUNDAI_IONIQ_5' or commit != SOURCE_COMMIT:
    raise ValueError('unsupported or missing vehicle/source provenance; verify baseline before extending')
  return records, digest


def summarize(rows):
  values = sorted(abs(r['error']) for r in rows if 'error' in r)
  return {'control_steps':len(rows), 'computed_steps':len(values),
          'median_abs_error':values[len(values)//2] if values else None,
          'p95_abs_error':values[min(len(values)-1, int(len(values)*.95))] if values else None,
          'max_abs_error':max(values) if values else None,
          'exclusions':dict(Counter(reason for r in rows for reason in r['reasons'])),
          'scope':'one_step_with_recorded_previous_command_not_closed_loop_or_exact_all_input_replay'}


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('logs', nargs='+', type=Path)
  parser.add_argument('--output', required=True, type=Path)
  args = parser.parse_args()
  records, inputs = [], []
  for path in args.logs:
    part, digest = read_local(path)
    records.extend(part)
    inputs.append({'name':path.name, 'sha256':digest})
  # Overlapping inputs would create false control discontinuities.
  ids = [(r['kind'], r['ns']) for r in records]
  if len(ids) != len(set(ids)):
    raise ValueError('duplicate service timestamps; provide non-overlapping logs')
  rows = audit(records)
  origin = rows[0]['ns'] if rows else 0
  for row in rows:
    row['relative_s'] = (row['ns']-origin)/1e9
  output = {'inputs':inputs, 'summary':summarize(rows), 'rows':rows}
  args.output.write_text(json.dumps(output, ensure_ascii=False, allow_nan=False))
  print(json.dumps(output['summary']))


if __name__ == '__main__':
  main()
