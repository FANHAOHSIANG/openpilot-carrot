"""Offline-only curvature experiment. Not for import by vehicle processes.

No vehicle interfaces, calibration, CAN, or actuator outputs. No road-use defaults.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Experiment:
  max_speed: float
  max_abs_curvature: float
  max_step: float
  tau: float
  max_gap: float

  def __post_init__(self):
    if not all(math.isfinite(x) and x > 0 for x in (self.max_speed, self.max_abs_curvature,
                                                    self.max_step, self.tau, self.max_gap)):
      raise ValueError('experiment parameters must be finite and positive')


class OfflineCandidate:
  def __init__(self, config):
    self.config = config
    self.reset()

  def reset(self):
    self.previous = None
    self.timestamp = None

  def step(self, *, enabled, valid, driver_override, turning, t, speed, target):
    """Return hypothetical target and whether smoothing was applied, for replay only."""
    if not math.isfinite(target):
      self.reset()
      raise ValueError('invalid target')
    cfg = self.config
    if (not enabled or not valid or driver_override or turning or
        not math.isfinite(t) or not math.isfinite(speed) or
        not 0 < speed <= cfg.max_speed or abs(target) > cfg.max_abs_curvature):
      self.reset()
      return target, False
    prev, last = self.previous, self.timestamp
    self.previous, self.timestamp = target, t
    if prev is None or not 0 < t - last <= cfg.max_gap or abs(target - prev) > cfg.max_step:
      return target, False
    alpha = -math.expm1(-(t - last) / cfg.tau)
    self.previous = prev + alpha * (target - prev)
    return self.previous, True
