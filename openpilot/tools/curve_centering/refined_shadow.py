"""Offline refinement R; requires an explicit differential-error assumption.

Retains C and U unchanged as falsification controls. Never used by controlsd.
Immediate proposal withdrawal does not reset the downstream production filter.
"""
from .centering_shadow import CenteringShadow, finite
from .uncertainty_shadow import GeometryBound, UncertaintyShadow


class RefinedShadow(UncertaintyShadow):
  def __init__(self):
    super().__init__(gain=.25)

  def update(self, row, bound=None):
    cfg = self.shadow.cfg
    t = row.get('model_t')
    samples = (row.get('geometry') or {}).get('samples', [])
    errors = [s.get('raw_error_m') for s in samples if s.get('x_m') == cfg.preview_m]
    tracking = row.get('lateral_accel_error_mps2')
    evidence_valid = (isinstance(bound, GeometryBound) and finite(t)
                      and bound.valid_from <= t <= bound.valid_until and bound.preview_m == cfg.preview_m)
    quality_valid = (row.get('eligible') is True and len(errors) == 1 and finite(errors[0])
                     and finite(tracking) and abs(tracking) <= cfg.max_tracking_error
                     and row.get('steering_saturated') is False and row.get('use_lane_lines') is False)
    # Loss of evidence/quality withdraws at the proposal boundary. Preserve
    # model time so a stale/reversed stream cannot restart admission unnoticed.
    withdrawn = not evidence_valid or not quality_valid
    if withdrawn:
      last_t = self.shadow.last_t
      self.shadow = CenteringShadow(cfg)
      self.shadow.last_t = last_t
      row = dict(row, eligible=False)
    result = super().update(row, bound)
    if withdrawn:
      result['reasons'] = sorted(set(result['reasons'] + ['refinement_evidence_or_quality_withdrawal']))
    result['scope'] = 'offline_refinement_assumed_interval_not_vehicle_control'
    return result
