"""Opt-in mode selection for carrotpilot; never filters acceleration commands."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class DecDecision:
  mode: str
  reason: str


class CarrotDEC:
  # Trial thresholds, not vehicle-calibrated comfort or stopping guarantees.
  ENTRY_TIME = 0.25
  RELEASE_TIME = 2.0
  BRAKE_ENTRY = -0.5
  BRAKE_URGENT = -1.5

  def __init__(self):
    self.reset()

  def reset(self):
    self.mode = 'acc'
    self.entry_time = 0.0
    self.clear_time = 0.0

  def update(self, *, enabled, experimental, original_mode, valid, engaged,
             override, carrot_state, soft_hold, speed, model_accel,
             model_stop, trajectory_speeds, trajectory_times, dt):
    if not enabled or not experimental:
      self.reset()
      return DecDecision(original_mode, 'disabled')

    values = (speed, model_accel, dt)
    trajectory_valid = (
      len(trajectory_speeds) == len(trajectory_times) == 33
      and all(math.isfinite(v) and v >= 0.0 for v in trajectory_speeds)
      and all(math.isfinite(t) for t in trajectory_times)
      and all(b > a for a, b in zip(trajectory_times, trajectory_times[1:]))
    )
    if not valid or not all(math.isfinite(v) for v in values) or speed < 0 or not 0 < dt <= 0.2 or not trajectory_valid:
      self.reset()
      return DecDecision(original_mode, 'invalid')

    if not engaged or override:
      self.reset()
      return DecDecision(original_mode, 'override')

    # Carrot's stop obstacle is only consumed by ACC MPC. Keep this constraint,
    # including signal-assist red holds, instead of swapping it for model E2E.
    if soft_hold or carrot_state in ('e2eStop', 'e2eStopped'):
      self.reset()
      return DecDecision('acc', 'carrot_stop')

    if carrot_state == 'e2ePrepare' or model_stop or model_accel <= self.BRAKE_URGENT:
      self.mode = 'blended'
      self.entry_time = 0.0
      self.clear_time = 0.0
      return DecDecision('blended', 'stop' if model_stop else 'urgent')

    # Only inspect the near-term horizon; far-future model speed routinely
    # trends toward a stop and must not keep ordinary cruise in E2E forever.
    near_speeds = [v for v, t in zip(trajectory_speeds, trajectory_times) if 0.5 <= t <= 2.0]
    slowing = (
      model_accel <= self.BRAKE_ENTRY
      or (speed > 2.0 and near_speeds and min(near_speeds) < speed - max(2.0, speed * 0.15))
    )
    if slowing:
      self.entry_time += dt
      self.clear_time = 0.0
      if self.entry_time + 1e-9 >= self.ENTRY_TIME:
        self.mode = 'blended'
    else:
      self.entry_time = 0.0
      self.clear_time += dt
      if self.clear_time + 1e-9 >= self.RELEASE_TIME:
        self.mode = 'acc'

    return DecDecision(self.mode, 'slowdown' if slowing else 'hold' if self.mode == 'blended' else 'cruise')
