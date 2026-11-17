"""100 Hz OFFLINE bridge: observer -> guarded C proposal -> production scalar path.

Default shadow output selects original model path. Explicit isolated mode selects
candidate curvature for an in-memory plant only. No messaging, Params, CAN, device
or actuator interface exists. Caller supplies consumed control inputs, not inferred
vehicle permissions. Unknown inputs stop the scalar trial; they never fabricate a
zero vehicle command. Continued smoothing after withdrawal is reported, not hidden.
"""
import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path

from .centering_shadow import CenteringShadow, finite
from .source_control import SourceControl


@dataclass(frozen=True)
class ControlTick:
  now_ns: int
  model_ns: int
  car_state_ns: int
  parameters_ns: int
  action: float
  speed: float
  feedback: float
  roll: float
  lat_active: bool
  driver_steering: bool
  driver_gas: bool
  driver_brake: bool
  maneuver: bool
  saturated: bool
  safety_limited: bool
  messages_valid: bool
  use_lane_lines: bool
  curve_speed: float
  lane_threshold: float
  vw_meb: bool


class ControlBridge:
  def __init__(self, mode='shadow'):
    if mode not in ('shadow', 'isolated'):
      raise ValueError('only shadow or isolated offline modes are supported')
    self.mode = mode
    self.source = SourceControl()
    self.shadow = CenteringShadow()
    self.last_ns = None
    self.last_observation = None
    self.last_model_ns = None
    self.proposal = None
    self.previous = {'A': 0.0, 'C': 0.0}
    self.started = {'A': False, 'C': False}

  def withdraw(self):
    self.shadow = CenteringShadow()
    self.proposal = None
    self.last_observation = None
    self.last_model_ns = None

  def step(self, tick, observation=None):
    t = tick
    result = {'mode': self.mode, 'vehicle_output': False, 'deployment_approved': False,
              'now_ns': t.now_ns, 'reasons': [], 'injected_delta_curvature': 0.0,
              'baseline': None, 'candidate': None, 'selected_curvature': None, 'residual_curvature': None,
              'same_state_baseline': None, 'policy_delta_curvature': None}
    reasons = result['reasons']
    times = (t.now_ns, t.model_ns, t.car_state_ns, t.parameters_ns)
    flags = (t.lat_active, t.driver_steering, t.driver_gas, t.driver_brake, t.maneuver, t.saturated,
             t.safety_limited, t.messages_valid, t.use_lane_lines, t.vw_meb)
    if (not all(type(n) is int and n >= 0 for n in times) or not all(type(f) is bool for f in flags)
        or not all(finite(v) for v in (t.action, t.speed, t.feedback, t.roll, t.curve_speed, t.lane_threshold))
        or t.speed < 0):
      reasons.append('invalid_control_input')
    elif (not t.messages_valid or not 0 <= t.now_ns-t.model_ns <= 200_000_000
          or not 0 <= t.now_ns-t.car_state_ns <= 30_000_000 or not 0 <= t.now_ns-t.parameters_ns <= 200_000_000):
      reasons.append('invalid_or_stale_control_input')
    if self.last_ns is not None and (type(t.now_ns) is not int or not 5_000_000 <= t.now_ns-self.last_ns <= 15_000_000):
      reasons.append('control_clock_gap_or_reversal')
    self.last_ns = t.now_ns if type(t.now_ns) is int else None
    if reasons:
      self.withdraw()
      self.previous = {'A': 0.0, 'C': 0.0}
      self.started = {'A': False, 'C': False}
      return result
    args = {'speed': t.speed, 'action': t.action, 'feedback': t.feedback, 'roll': t.roll, 'active': t.lat_active,
                'use_lane_lines': t.use_lane_lines, 'curve_speed': t.curve_speed, 'lane_threshold': t.lane_threshold, 'vw_meb': t.vw_meb}
    try:
      baseline = self.source.step(**args, previous=self.previous['A'], lateral_started=self.started['A'])
    except ValueError:
      self.withdraw()
      self.previous = {'A': 0.0, 'C': 0.0}
      self.started = {'A': False, 'C': False}
      reasons.append('unsupported_lane_or_vw_mode')
      return result
    if not t.lat_active:
      reasons.append('lateral_inactive')
    if t.driver_steering or t.driver_gas or t.driver_brake:
      reasons.append('driver_override')
    if t.maneuver:
      reasons.append('maneuver')
    if t.saturated or t.safety_limited:
      reasons.append('saturation_or_safety_limit')
    if t.speed < self.shadow.cfg.min_speed:
      reasons.append('low_speed')
    row = observation.get('row') if isinstance(observation, dict) else None
    if not isinstance(row, dict):
      reasons.append('missing_observation')
    else:
      ns, available = observation.get('model_ns'), observation.get('available_ns')
      if (type(ns) is not int or ns != t.model_ns or type(available) is not int
          or not ns <= available <= t.now_ns or t.now_ns-available > 200_000_000
          or not finite(row.get('model_t')) or abs(row['model_t']-ns/1e9) > 1e-9
          or not finite(row.get('t')) or not ns/1e9-1e-9 <= row['t'] <= available/1e9+1e-9
          or row.get('model_action_curvature') != t.action):
        reasons.append('unmatched_stale_or_future_observation')
      if (row.get('eligible') is not True or row.get('lat_active') is not True
          or row.get('driver_pressed') is not False or row.get('lane_change_state') != 'off'
          or row.get('desire') != 'none' or row.get('steering_saturated') is not False
          or row.get('reasons') != [] or not finite(row.get('lateral_accel_error_mps2'))
          or abs(row['lateral_accel_error_mps2']) > self.shadow.cfg.max_tracking_error):
        reasons.append('observer_gate')
      geometry = row.get('geometry')
      samples = geometry.get('samples') if isinstance(geometry, dict) else None
      if (not isinstance(samples, list) or not all(isinstance(s, dict) for s in samples)
          or not any(s.get('x_m') == self.shadow.cfg.preview_m and finite(s.get('raw_error_m')) for s in samples)):
        reasons.append('invalid_geometry')
      if self.last_model_ns is not None:
        if ns == self.last_model_ns and observation != self.last_observation:
          reasons.append('mutated_same_model_observation')
        elif type(ns) is not int or ns < self.last_model_ns:
          reasons.append('reversed_model_id')
    if reasons:
      self.withdraw()
    elif t.model_ns != self.last_model_ns:
      # Real selected source is the production mode expression, not the planner's
      # raw useLaneLines flag. Current consumed speed/permissions override old rows.
      row = dict(row, speed_kph=t.speed*3.6, use_lane_lines=False)
      self.proposal = self.shadow.update(row)
      self.last_observation = deepcopy(observation)
      self.last_model_ns = t.model_ns
    delta = 0.0 if self.proposal is None else self.proposal['delta_accel']/t.speed**2
    if self.proposal is not None and not self.proposal['active_candidate']:
      reasons.extend(self.proposal['reasons'])
    same_state = self.source.step(**args, previous=self.previous['C'], lateral_started=self.started['C'])
    candidate = self.source.step(**dict(args, action=t.action+delta),
                                 previous=self.previous['C'], lateral_started=self.started['C'])
    for arm, output in (('A', baseline), ('C', candidate)):
      self.previous[arm] = output['curvature']
      self.started[arm] = output['lateral_started']
    result.update(baseline=baseline, candidate=candidate, injected_delta_curvature=delta,
                  same_state_baseline=same_state, policy_delta_curvature=candidate['curvature']-same_state['curvature'],
                  selected_curvature=(baseline if self.mode == 'shadow' else candidate)['curvature'],
                  residual_curvature=candidate['curvature']-baseline['curvature'])
    return result


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('ticks', type=Path, help='local JSONL: {tick: ControlTick fields, observation: envelope}')
  parser.add_argument('--mode', choices=('shadow', 'isolated'), default='shadow')
  parser.add_argument('--output', type=Path, required=True)
  args = parser.parse_args()
  bridge = ControlBridge(args.mode)
  counts = Counter()
  # Exclusive creation prevents replacing input or another report.
  with args.ticks.open() as source, args.output.open('x') as output:
    for line in source:
      item = json.loads(line)
      result = bridge.step(ControlTick(**item['tick']), item.get('observation'))
      output.write(json.dumps(result, allow_nan=False)+'\n')
      counts.update(result['reasons'])
  print(json.dumps({'mode': args.mode, 'vehicle_output': False, 'reasons': dict(counts)}))


if __name__ == '__main__':
  main()
