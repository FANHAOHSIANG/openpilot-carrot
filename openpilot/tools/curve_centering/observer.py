"""Model/plan geometry comparison shared by offline replay and live observation.

Coordinates: x forward, y right. Lane confidence is a model estimate, not truth.
Only exact modelMonoTime matches are compared; no extrapolation or CAN writes.
"""

from bisect import bisect_right
from collections import deque
from dataclasses import asdict, dataclass
import math
from statistics import median


@dataclass(frozen=True)
class Config:
  min_lane_probability: float = 0.7
  max_lane_std_m: float = 0.3
  min_lane_width_m: float = 2.5
  max_lane_width_m: float = 4.5
  max_width_variation_m: float = 0.7
  max_input_age_s: float = 0.2
  max_plan_age_s: float = 0.3
  min_speed_mps: float = 5.0
  lane_change_recovery_s: float = 2.0
  stable_geometry_s: float = 1.0
  bias_threshold_m: float = 0.2
  # Vehicle center y relative to model coordinate origin. None means uncalibrated.
  vehicle_center_y_m: float | None = None
  vehicle_width_m: float | None = None

  def __post_init__(self):
    for key, value in asdict(self).items():
      if value is not None and (not math.isfinite(value) or (key != 'vehicle_center_y_m' and value <= 0)):
        raise ValueError(f'invalid {key}')
    if self.min_lane_probability > 1 or self.min_lane_width_m >= self.max_lane_width_m:
      raise ValueError('invalid lane confidence/width thresholds')


def finite(value):
  return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def curve(points):
  """Validate a forward polyline. Reject duplicates, truncation, NaN and reversal."""
  x, y = points.get('x', []), points.get('y', [])
  if len(x) < 3 or len(x) != len(y) or not all(finite(v) for v in [*x, *y]):
    raise ValueError('invalid_polyline')
  if any(b <= a for a, b in zip(x[:-1], x[1:], strict=True)):
    raise ValueError('nonmonotonic_polyline')
  return x, y


def at(poly, x):
  xs, ys = poly
  if not xs[0] <= x <= xs[-1]:
    raise ValueError('insufficient_horizon')
  i = min(max(bisect_right(xs, x) - 1, 0), len(xs) - 2)
  return ys[i] + (ys[i + 1] - ys[i]) * (x - xs[i]) / (xs[i + 1] - xs[i])


def slope(poly, x):
  lo, hi = max(poly[0][0], x - 1), min(poly[0][-1], x + 1)
  if hi - lo < 0.01:
    raise ValueError('insufficient_horizon')
  return (at(poly, hi) - at(poly, lo)) / (hi - lo)


def geometry(model, plan, cfg):
  lanes = model.get('laneLines', [])
  probs, stds = model.get('laneLineProbs', []), model.get('laneLineStds', [])
  if len(lanes) < 3 or len(probs) < 3 or len(stds) < 3:
    raise ValueError('missing_lanes')
  if any(
    not finite(probs[i]) or not 0 <= probs[i] <= 1 or probs[i] < cfg.min_lane_probability or not finite(stds[i]) or not 0 <= stds[i] <= cfg.max_lane_std_m
    for i in (1, 2)
  ):
    raise ValueError('uncertain_lanes')
  left, right = curve(lanes[1]), curve(lanes[2])
  raw = curve(model.get('position', {}))
  ys = plan.get('dPathPoints', [])
  # In this branch dPathPoints are MPC inputs, paired with model.position.x.
  if len(ys) > len(raw[0]):
    raise ValueError('invalid_plan_shape')
  requested = curve({'x': raw[0][: len(ys)], 'y': ys})
  solved = curve(plan.get('position', {}))
  horizon = min(left[0][-1], right[0][-1], raw[0][-1], requested[0][-1], solved[0][-1], 30.0)
  if horizon < 10 or max(p[0][0] for p in (left, right, raw, requested, solved)) > 0:
    raise ValueError('insufficient_horizon')
  xs = [float(x) for x in range(0, int(horizon) + 1, 2)]
  if xs[-1] < horizon:
    xs.append(horizon)
  center = (xs, [(at(left, x) + at(right, x)) / 2 for x in xs])
  widths = [(at(right, x) - at(left, x)) / math.hypot(1, slope(center, x)) for x in xs]
  if any(not cfg.min_lane_width_m <= w <= cfg.max_lane_width_m for w in widths):
    raise ValueError('implausible_lane_width')
  if max(widths) - min(widths) > cfg.max_width_variation_m:
    raise ValueError('changing_lane_width')
  samples = []
  for x in (10.0, 20.0, 30.0):
    if x > horizon:
      continue
    scale = math.hypot(1, slope(center, x))
    c = at(center, x)
    samples.append(
      {'x_m': x, 'raw_error_m': (at(raw, x) - c) / scale, 'request_error_m': (at(requested, x) - c) / scale, 'mpc_error_m': (at(solved, x) - c) / scale}
    )

  def curvature(x):
    h = 2.0
    return (at(center, x + h) - 2 * at(center, x) + at(center, x - h)) / (h * h) / math.hypot(1, slope(center, x)) ** 3

  near_k, far_k = curvature(4.0), curvature(min(horizon - 2, 20.0))
  origin_offset = -at(center, 0) / math.hypot(1, slope(center, 0))
  body_offset = None if cfg.vehicle_center_y_m is None else (cfg.vehicle_center_y_m - at(center, 0)) / math.hypot(1, slope(center, 0))
  clearance = None
  if body_offset is not None and cfg.vehicle_width_m is not None:
    clearance = min(widths[0] / 2 + body_offset, widths[0] / 2 - body_offset) - cfg.vehicle_width_m / 2
  return {
    'lane_probability_min': min(probs[1:3]),
    'lane_width_m': widths[0],
    'horizon_m': horizon,
    'origin_offset_m': origin_offset,
    'vehicle_offset_m': body_offset,
    'estimated_body_clearance_m': clearance,
    'near_curvature_right_positive': near_k,
    'far_curvature_right_positive': far_k,
    'samples': samples,
    'request_bias_m': median(s['request_error_m'] for s in samples),
    'raw_bias_m': median(s['raw_error_m'] for s in samples),
    'mpc_bias_m': median(s['mpc_error_m'] for s in samples),
    'plot': {
      'x': xs,
      'left': [at(left, x) for x in xs],
      'right': [at(right, x) for x in xs],
      'center': center[1],
      'raw': [at(raw, x) for x in xs],
      'request': [at(requested, x) for x in xs],
      'mpc': [at(solved, x) for x in xs],
    },
  }


class Observer:
  """Bounded caches; inspect telemetry only. Never supplies an actuator target."""

  def __init__(self, config=None):
    self.config = config or Config()
    self.history = {k: deque(maxlen=128) for k in ('modelV2', 'carState', 'carControl', 'controlsState')}
    self.last_plan_time = None
    self.last_maneuver = None
    self.geometry_since = None
    self.previous_geometry = None

  def reset_temporal(self):
    self.last_maneuver = self.geometry_since = self.previous_geometry = None

  def _before(self, kind, timestamp):
    eligible = [r for r in self.history[kind] if r['t'] <= timestamp]
    return max(eligible, key=lambda r: r['t']) if eligible else None

  def feed(self, record):
    kind, t = record['kind'], record['t']
    if not finite(t):
      return None
    if kind in self.history:
      self.history[kind].append(record)
      return None
    if kind != 'lateralPlan':
      return None
    cfg, plan = self.config, record['data']
    out = {
      't': t,
      'model_t': plan.get('modelMonoTime', 0) / 1e9,
      'eligible': False,
      'reasons': [],
      'findings': [],
      'geometry': None,
      'phase': 'unknown',
      'direction': 'unknown',
      'use_lane_lines': plan.get('useLaneLines', False),
      'mode': 'observe_only',
    }
    reasons = out['reasons']
    if self.last_plan_time is not None:
      if t <= self.last_plan_time:
        reasons.append('nonmonotonic_plan')
        return out
      if t - self.last_plan_time > cfg.max_plan_age_s:
        self.reset_temporal()
    self.last_plan_time = t
    model_ns = plan.get('modelMonoTime', 0)
    model = next((r for r in reversed(self.history['modelV2']) if r.get('mono_ns') == model_ns), None)
    if model is None:
      reasons.append('unmatched_model')
      self.geometry_since = None
      return out
    mt = model['t']
    if not 0 <= t - mt <= cfg.max_plan_age_s:
      reasons.append('stale_or_future_model')
    if not record.get('valid', False) or not model.get('valid', False) or not plan.get('mpcSolutionValid', False):
      reasons.append('invalid_model_or_plan')
    states = {k: self._before(k, mt) for k in ('carState', 'carControl', 'controlsState')}
    for k, state in states.items():
      if state is None or not state.get('valid', False) or not 0 <= mt - state['t'] <= cfg.max_input_age_s:
        reasons.append('stale_' + k)
    if reasons:
      self.geometry_since = None
      return out
    cs, cc, controls = (states[k]['data'] for k in ('carState', 'carControl', 'controlsState'))
    # MPC geometry can exist while controlsd uses model action directly.
    # Commands are the latest at/before the model timestamp, not its future response.
    for key, value in (
      ('model_action_curvature', model['data'].get('action', {}).get('desiredCurvature')),
      ('command_curvature', cc.get('actuators', {}).get('curvature')),
      ('estimated_curvature', controls.get('curvature')),
    ):
      out[key] = value if finite(value) else None
    speed = cs.get('vEgo')
    if not finite(speed) or speed < 0:
      reasons.append('invalid_speed')
      self.geometry_since = None
      return out
    out['speed_kph'] = speed * 3.6
    out['input_ages_ms'] = {k: (mt - v['t']) * 1000 for k, v in states.items()}
    out['plan_latency_ms'] = (t - mt) * 1000
    out['driver_pressed'] = bool(cs.get('steeringPressed', False))
    out['lat_active'] = bool(cc.get('latActive', False))
    meta = model['data'].get('meta', {})
    state, desire = meta.get('laneChangeState'), meta.get('desire')
    out['lane_change_state'], out['desire'] = state, desire
    maneuver = state != 'off' or desire != 'none' or cs.get('leftBlinker') or cs.get('rightBlinker')
    if maneuver:
      self.last_maneuver = t
      reasons.append('maneuver')
    elif self.last_maneuver is not None and t - self.last_maneuver < cfg.lane_change_recovery_s:
      reasons.append('maneuver_recovery')
    if not out['lat_active']:
      reasons.append('lateral_inactive')
    if out['driver_pressed'] or cs.get('gasPressed') or cs.get('brakePressed'):
      reasons.append('driver_override')
    if speed < cfg.min_speed_mps:
      reasons.append('low_speed')
    try:
      g = geometry(model['data'], plan, cfg)
    except (ValueError, TypeError, KeyError, IndexError) as exc:
      reasons.append(str(exc) if isinstance(exc, ValueError) else 'invalid_geometry')
      self.geometry_since = self.previous_geometry = None
      return out
    out['geometry'] = g
    previous = self.previous_geometry
    if previous is not None and (abs(g['origin_offset_m'] - previous['origin_offset_m']) > 0.4 or abs(g['lane_width_m'] - previous['lane_width_m']) > 0.35):
      reasons.append('lane_geometry_jump')
      self.geometry_since = None
    self.previous_geometry = g
    if reasons:
      self.geometry_since = None
    elif self.geometry_since is None:
      self.geometry_since = t
    if self.geometry_since is None or t - self.geometry_since < cfg.stable_geometry_s:
      reasons.append('warming_up')
    k0, k1 = g['near_curvature_right_positive'], g['far_curvature_right_positive']
    a0, a1 = abs(k0) * speed**2, abs(k1) * speed**2
    out['phase'] = 'straight' if max(a0, a1) < 0.4 else ('approach' if a0 < 0.4 else ('exit' if a1 < a0 * 0.5 else 'curve'))
    k = k1 if abs(k1) > abs(k0) else k0
    out['direction'] = 'straight' if out['phase'] == 'straight' else ('right' if k > 0 else 'left')
    g['inward_request_bias_m'] = None if out['direction'] == 'straight' else g['request_bias_m'] * (1 if k > 0 else -1)
    lateral = controls.get('lateralControlState', {})
    torque = lateral.get('torqueState', {})
    actual, desired = torque.get('actualLateralAccel'), torque.get('desiredLateralAccel')
    out['lateral_accel_error_mps2'] = desired - actual if finite(actual) and finite(desired) and torque.get('active') else None
    out['steering_saturated'] = any(v.get('saturated', False) for v in lateral.values() if isinstance(v, dict))
    out['eligible'] = not reasons
    # Findings are review cues, not diagnosed causes or automatic parameter changes.
    if out['eligible']:
      if abs(g['request_bias_m']) > cfg.bias_threshold_m:
        out['findings'].append('requested_path_bias')
      if abs(g['raw_bias_m']) > cfg.bias_threshold_m:
        out['findings'].append('raw_model_path_bias')
      if not out['use_lane_lines']:
        out['findings'].append('lane_centering_inactive')
      if out['steering_saturated']:
        out['findings'].append('steering_saturated')
      if out['lateral_accel_error_mps2'] is not None and abs(out['lateral_accel_error_mps2']) > 0.3:
        out['findings'].append('lateral_response_mismatch')
    return out


SERVICES = ('modelV2', 'carState', 'carControl', 'controlsState', 'lateralPlan')


def from_event(event):
  kind = event.which()
  if kind not in SERVICES:
    return None
  return {'kind': kind, 'mono_ns': int(event.logMonoTime), 't': event.logMonoTime / 1e9, 'valid': bool(event.valid), 'data': getattr(event, kind).to_dict()}
