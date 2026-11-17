"""Offline research candidate, not connected to controlsd or vehicle outputs.

Uses relative model-path/lane-center geometry; it is NOT calibrated body error.
Limits below are experimental comparison settings, not validated road settings.
The output is an unactuated proposal before production 100 Hz control limits.
"""
import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path


@dataclass(frozen=True)
class ShadowConfig:
  preview_m: float = 20.0
  max_delta_accel: float = 0.25
  delta_accel_rate: float = 0.25
  stable_s: float = 1.0
  max_tracking_error: float = 0.2
  max_gap_s: float = 0.2
  min_speed: float = 5.0

  def __post_init__(self):
    if any(not math.isfinite(v) or v <= 0 for v in asdict(self).values()):
      raise ValueError('invalid shadow config')


def finite(x):
  return isinstance(x, (float, int)) and not isinstance(x, bool) and math.isfinite(x)


class CenteringShadow:
  def __init__(self, cfg=ShadowConfig()):
    self.cfg = cfg
    self.last_t = self.good_since = None
    self.delta_accel = 0.0

  def update(self, row):
    cfg = self.cfg
    t = row.get('model_t')
    action = row.get('model_action_curvature', (row.get('model_action') or {}).get('desiredCurvature'))
    speed = row.get('speed_kph')
    reasons = list(row.get('reasons', []))
    previous_t = self.last_t
    valid_time = finite(t) and (previous_t is None or 0 < t-previous_t <= cfg.max_gap_s)
    dt = t-previous_t if valid_time and previous_t is not None else 0.0
    self.last_t = t if finite(t) else None
    hard = (not valid_time or not finite(action) or not finite(speed) or speed/3.6 < cfg.min_speed
            or row.get('driver_pressed') or not row.get('lat_active')
            or row.get('lane_change_state') != 'off' or row.get('desire') != 'none'
            or any(x in reasons for x in ('driver_override', 'maneuver', 'maneuver_recovery')))
    if hard:
      self.delta_accel = 0.0
      self.good_since = None
      reasons.append('withdraw_immediately_invalid_or_driver_or_maneuver')
    error = None
    g = row.get('geometry') or {}
    for sample in g.get('samples', []):
      if sample.get('x_m') == cfg.preview_m and finite(sample.get('raw_error_m')):
        error = sample['raw_error_m']
    tracking = row.get('lateral_accel_error_mps2')
    if not finite(tracking):
      reasons.append('tracking_unavailable')
    elif abs(tracking) > cfg.max_tracking_error:
      reasons.append('tracking_error_high')
    if row.get('steering_saturated') is not False:
      reasons.append('saturation_or_unknown')
    if row.get('use_lane_lines') is not False:
      reasons.append('not_model_mode')
    if error is None:
      reasons.append('preview_geometry_unavailable')
    good = (not hard and row.get('eligible') is True and error is not None
            and finite(tracking) and abs(tracking) <= cfg.max_tracking_error
            and row.get('steering_saturated') is False and row.get('use_lane_lines') is False)
    if not good:
      self.good_since = None
      reasons.append('observer_geometry_tracking_or_mode_gate')
    elif self.good_since is None:
      self.good_since = t
    ready = good and t-self.good_since >= cfg.stable_s
    target = 0.0
    if ready:
      target = max(-cfg.max_delta_accel, min(cfg.max_delta_accel, -2*error*(speed/3.6)**2/cfg.preview_m**2))
    elif good:
      reasons.append('candidate_warmup')
    if not hard:
      step = cfg.delta_accel_rate * dt
      self.delta_accel += max(-step, min(step, target-self.delta_accel))
    delta_k = self.delta_accel/(speed/3.6)**2 if finite(speed) and speed/3.6 >= cfg.min_speed else 0.0
    return {'model_t':t if finite(t) else None, 'active_candidate':ready,
            'proposal_curvature':action+delta_k if finite(action) else None,
            'model_action':action if finite(action) else None, 'delta_curvature':delta_k,
            'delta_accel':self.delta_accel, 'relative_path_error_m':error,
            'geometric_shift_proxy_m':delta_k*cfg.preview_m**2/2,
            'reasons':sorted(set(reasons)),
            'scope':'offline_unactuated_relative_geometry_not_vehicle_clearance'}


def compare(rows, cfg=ShadowConfig()):
  shadow = CenteringShadow(cfg)
  output = [shadow.update(r) for r in rows]
  active = [r for r in output if r['active_candidate']]
  return {'config':asdict(cfg), 'summary':{
    'frames':len(output), 'candidate_frames':len(active),
    'nonzero_correction_frames':sum(abs(r['delta_accel']) > 1e-12 for r in output),
    'max_abs_delta_accel':max((abs(r['delta_accel']) for r in output), default=0),
    'max_abs_geometric_shift_proxy_m':max((abs(r['geometric_shift_proxy_m']) for r in output), default=0),
    'reason_counts':dict(Counter(x for r in output for x in r['reasons']))}, 'rows':output}


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('observer_json', type=Path)
  parser.add_argument('--output', type=Path, required=True)
  args = parser.parse_args()
  data = json.loads(args.observer_json.read_text())
  # One continuous chronological stream; invoke separately for independent routes.
  output = compare(data['rows'])
  args.output.write_text(json.dumps(output, allow_nan=False))
  print(json.dumps(output['summary']))


if __name__ == '__main__':
  main()
