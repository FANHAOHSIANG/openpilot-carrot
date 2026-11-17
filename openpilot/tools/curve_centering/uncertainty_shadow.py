"""Offline uncertainty experiment. No control, Params, messaging or CAN output.

The bound concerns DIFFERENTIAL model-path/lane geometry error, not a common
camera translation (which cancels in that comparison), nor body-center error.
A caller-supplied bound is an assumption, not evidence of real calibration.
"""
from dataclasses import dataclass
from copy import deepcopy

from openpilot.tools.curve_centering.centering_shadow import CenteringShadow, ShadowConfig, finite


@dataclass(frozen=True)
class GeometryBound:
  error_bound_m: float
  preview_m: float
  valid_from: float
  valid_until: float
  reference: str

  def __post_init__(self):
    if (not all(finite(x) for x in (self.error_bound_m, self.preview_m, self.valid_from, self.valid_until))
        or self.error_bound_m < 0 or self.preview_m <= 0 or self.valid_until < self.valid_from
        or not isinstance(self.reference, str) or not self.reference.strip()):
      raise ValueError('invalid geometry uncertainty assumption')


def nearest_zero_error(error, bound):
  """Nearest point to zero in [error-bound, error+bound]; never invent a sign."""
  if not finite(error) or not finite(bound) or bound < 0:
    raise ValueError('invalid interval')
  return max(error-bound, 0.0) if error >= 0 else min(error+bound, 0.0)


class UncertaintyShadow:
  def __init__(self, cfg=ShadowConfig(), *, gain=0.5):
    if not finite(gain) or not 0 < gain <= 1:
      raise ValueError('gain must be in (0, 1]')
    self.shadow = CenteringShadow(cfg)
    self.gain = gain

  def update(self, row, bound=None):
    copied = deepcopy(row)
    reasons = list(copied.get('reasons', []))
    t = row.get('model_t')
    valid = (isinstance(bound, GeometryBound) and finite(t)
             and bound.valid_from <= t <= bound.valid_until
             and bound.preview_m == self.shadow.cfg.preview_m)
    robust_error = None
    if valid:
      for sample in (copied.get('geometry') or {}).get('samples', []):
        if sample.get('x_m') == bound.preview_m and finite(sample.get('raw_error_m')):
          robust_error = nearest_zero_error(sample['raw_error_m'], bound.error_bound_m)
          sample['raw_error_m'] = self.gain * robust_error
      if robust_error == 0:
        reasons.append('geometry_direction_uncertain')
    else:
      copied['eligible'] = False
      copied['geometry'] = None
      reasons.append('geometry_bound_missing_expired_or_mismatched')
    copied['reasons'] = reasons
    result = self.shadow.update(copied)
    result.update(robust_error_m=robust_error, uncertainty_gain=self.gain,
                  bound_reference=bound.reference if valid else None,
                  scope='offline_assumed_error_interval_not_calibrated_body_center')
    return result
