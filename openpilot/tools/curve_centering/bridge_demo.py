"""Generate synthetic observer inputs and exercise both offline control bridge modes.

Fixed-input fault injection, NOT a closed-loop plant or vehicle replay. All flags,
geometry and torque tracking here are synthetic assumptions. No device access.
"""
import argparse
from collections import Counter
from dataclasses import asdict, replace
import json
from pathlib import Path

from .control_bridge import ControlBridge, ControlTick
from .observer import Observer

FAULTS = {
  4: 'driver_steering', 6: 'driver_gas', 8: 'driver_brake', 10: 'maneuver',
  12: 'geometry', 14: 'stale_model', 16: 'tracking', 18: 'saturated',
  20: 'safety_limited', 22: 'lane_mode', 24: 'vw_mode', 26: 'inactive',
  28: 'low_speed', 30: 'missing_observation',
}


def synthetic_records(ns, *, fault='none'):
  """Full Observer messages, not a hand-authored eligible verdict."""
  t = ns/1e9
  xs = [float(x) for x in range(0, 42, 2)]

  def path(bias):
    return {'x': xs, 'y': [.001*x*x/2+bias for x in xs]}

  model = {'laneLines': [path(-5.4), path(-1.8), path(1.8), path(5.4)],
           'laneLineProbs': [.9]*4, 'laneLineStds': [.1]*4, 'position': path(.5),
           'meta': {'laneChangeState': 'off', 'desire': 'none'}, 'action': {'desiredCurvature': .001}}
  if fault == 'geometry':
    model['laneLineProbs'] = [0.]*4
  data = {
    'carState': {'vEgo': 12., 'steeringPressed': fault == 'driver_steering',
                 'gasPressed': fault == 'driver_gas', 'brakePressed': fault == 'driver_brake',
                 'leftBlinker': fault == 'maneuver', 'rightBlinker': False},
    'carControl': {'latActive': fault != 'inactive', 'actuators': {'curvature': .001}},
    'controlsState': {'curvature': .001, 'lateralControlState': {'torqueState': {
      'active': True, 'saturated': fault == 'saturated', 'actualLateralAccel': .144,
      'desiredLateralAccel': .5 if fault == 'tracking' else .144}}},
    'modelV2': model,
    'lateralPlan': {'modelMonoTime': ns, 'mpcSolutionValid': True, 'useLaneLines': fault == 'lane_mode',
                    'dPathPoints': path(0.)['y'], 'position': path(0.)},
  }
  return [{'kind': k, 'mono_ns': ns, 't': t, 'valid': True, 'data': v} for k, v in data.items()]


def demo_ticks(seconds=35):
  observer = Observer()
  observation = None
  model_ns = 0
  for i in range(seconds*100):
    ns = i*10_000_000
    fault = FAULTS.get(i//100, 'none')
    if i % 5 == 0 and fault != 'stale_model':
      model_ns = ns
      for record in synthetic_records(ns, fault=fault):
        row = observer.feed(record)
        if row is not None:
          observation = {'model_ns': model_ns, 'available_ns': ns, 'row': row}
    tick = ControlTick(ns, model_ns, ns, ns, .001, 12., .001, 0., True,
                       False, False, False, False, False, False, True, False, 0., 0., False)
    if fault in ('driver_steering', 'driver_gas', 'driver_brake', 'maneuver', 'saturated', 'safety_limited'):
      tick = replace(tick, **{fault: True})
    elif fault == 'lane_mode':
      tick = replace(tick, use_lane_lines=True, curve_speed=30., lane_threshold=20.)
    elif fault == 'vw_mode':
      tick = replace(tick, vw_meb=True)
    elif fault == 'inactive':
      tick = replace(tick, lat_active=False)
    elif fault == 'low_speed':
      tick = replace(tick, speed=4.)
    yield tick, None if fault == 'missing_observation' else observation, fault


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--output', type=Path, required=True, help='new local directory (must not already exist)')
  args = parser.parse_args()
  args.output.mkdir(parents=True, exist_ok=False)
  bridges = {mode: ControlBridge(mode) for mode in ('shadow', 'isolated')}
  counts = {mode: Counter() for mode in bridges}
  maxima = dict.fromkeys(bridges, 0.0)
  active = dict.fromkeys(bridges, 0)
  residual_withdrawals = dict.fromkeys(bridges, 0)
  with (args.output/'inputs.jsonl').open('x') as source, (args.output/'results.jsonl').open('x') as sink:
    for tick, observation, fault in demo_ticks():
      source.write(json.dumps({'tick': asdict(tick), 'observation': observation}, allow_nan=False)+'\n')
      outputs = {}
      for mode, bridge in bridges.items():
        r = outputs[mode] = bridge.step(tick, observation)
        counts[mode].update(r['reasons'])
        active[mode] += r['injected_delta_curvature'] != 0
        maxima[mode] = max(maxima[mode], abs(r['residual_curvature'] or 0.))
        residual_withdrawals[mode] += r['injected_delta_curvature'] == 0 and abs(r['residual_curvature'] or 0.) > 1e-12
      sink.write(json.dumps({'fault': fault, **outputs}, allow_nan=False)+'\n')
  summary = {'scope': 'synthetic_fixed_input_pre_LaC_no_plant_no_CAN', 'deployment_approved': False,
             'ticks': 3500, 'reason_counts': {k: dict(v) for k, v in counts.items()},
             'nonzero_injection_ticks': active, 'max_curvature_difference': maxima,
             'withdrawn_but_smoothing_residual_ticks': residual_withdrawals}
  (args.output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
  print(json.dumps(summary, indent=2))


if __name__ == '__main__':
  main()
