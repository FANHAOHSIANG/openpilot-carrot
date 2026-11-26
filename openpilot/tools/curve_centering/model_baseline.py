"""Offline non-VW model baseline. Inputs must be consumed 100 Hz control inputs.

Planner-rate rows cannot reproduce a complete control sequence. This module
has no messaging/Params/CAN access and deliberately rejects lane/VW branches.
"""
from dataclasses import dataclass
import math

SOURCE_COMMIT = '0e462225e4184df0ee4e8cfda7b4cc7f69fbbf38'
DT_CTRL = 0.01


@dataclass(frozen=True)
class ModelStep:
  curvature: float
  smoothed_curvature: float
  rate_limited: bool
  curvature_limited: bool  # Original flag excludes rate-only limiting.
  source: str


def model_step(*, speed: float, previous: float, action: float, feedback: float,
               roll: float, active: bool, lateral_started: bool,
               lane_mode: bool = False, vw_meb: bool = False) -> ModelStep:
  """Reproduce pinned controlsd selection and clip_curvature, one control step.

  lateral_started is the process-lifetime flag, not preceding latActive. The
  pinned source does not clear it at disengagement. Caller owns state and must
  report invalid/unsupported samples rather than substitute fabricated inputs.
  """
  if lane_mode or vw_meb:
    raise ValueError('lane/VW branch requires a separate verified baseline')
  if not all(math.isfinite(v) for v in (speed, previous, action, feedback, roll)):
    raise ValueError('non-finite control input')
  if active and not lateral_started:
    previous = feedback
  if active:
    alpha = 1 - math.exp(-DT_CTRL / 0.1)
    requested = alpha * action + (1 - alpha) * previous
  else:
    requested = feedback
  v = max(speed, 1.0)
  step = 5.0 / v**2 * DT_CTRL
  rate_clipped = min(max(requested, previous - step), previous + step)
  fraction = min(max((v - 80 / 3.6) / (120 / 3.6 - 80 / 3.6), 0.0), 1.0)
  allowance = 4.5 + fraction * (3.0 - 4.5)
  roll_accel = roll * 9.81
  accel_clipped = min(max(rate_clipped, (-allowance + roll_accel) / v**2), (allowance + roll_accel) / v**2)
  result = min(max(accel_clipped, -0.2), 0.2)
  return ModelStep(result, requested, rate_clipped != requested,
                   accel_clipped != rate_clipped or result != accel_clipped,
                   'model_action' if active else 'inactive_feedback')
