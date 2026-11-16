"""HCOP-inspired roadside and tracked-vehicle offset *candidates*, never commands.

Coordinates match modelV2: x forward, y right. Negative offset means left.
The learned Custin bend compensation and HCOP camera shear are NOT imported.
"""
from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class Config:
  max_offset_m: float = 0.15
  rate_mps: float = 0.05
  vehicle_width_m: float = 2.0
  line_margin_m: float = 0.35
  confirm_s: float = 0.8
  max_gap_s: float = 0.25
  min_speed_mps: float = 20 / 3.6
  max_curvature: float = 0.002

  def __post_init__(self):
    bounds = {
      'max_offset_m': (0, 0.30), 'rate_mps': (0.01, 0.10), 'vehicle_width_m': (1.5, 3.0),
      'line_margin_m': (0.25, 1.0), 'confirm_s': (0.5, 3.0), 'max_gap_s': (0.05, 0.30),
      'min_speed_mps': (5, 30), 'max_curvature': (0.0001, 0.003),
    }
    for name, (lo, hi) in bounds.items():
      value = getattr(self, name)
      if not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError(f'invalid {name}')


def sample(line, xs):
  """Interpolate in physical x, rejecting missing coverage rather than extrapolating."""
  x, y = np.asarray(line['x'], dtype=float), np.asarray(line['y'], dtype=float)
  if (x.ndim != 1 or y.shape != x.shape or len(x) < 2 or not np.isfinite(x).all()
      or not np.isfinite(y).all() or not np.all(np.diff(x) > 0) or min(xs) < x[0] or max(xs) > x[-1]):
    raise ValueError('invalid or short geometry')
  return np.interp(xs, x, y)


def geometry(snapshot, cfg):
  if snapshot.get('valid') is not True:
    raise ValueError(snapshot.get('export_reason', 'invalid snapshot'))
  speed, curvature = float(snapshot['speed_mps']), float(snapshot['curvature'])
  if not math.isfinite(speed) or not math.isfinite(curvature):
    raise ValueError('nonfinite driving state')
  if not 0 <= float(snapshot['model_age_s']) <= cfg.max_gap_s:
    raise ValueError('invalid or stale model')
  if not snapshot['lat_active'] or snapshot['steering_pressed'] or snapshot['blinker'] or snapshot['maneuver']:
    raise ValueError('inactive or driver/maneuver override')
  if speed < cfg.min_speed_mps or abs(curvature) > cfg.max_curvature:
    raise ValueError('speed or curve gate')
  lines, probs = snapshot['lane_lines'], snapshot['lane_probs']
  if len(lines) != 4 or len(probs) != 4 or not all(math.isfinite(p) and 0 <= p <= 1 for p in probs):
    raise ValueError('invalid lane probabilities')
  if min(probs[1:3]) < 0.8:
    raise ValueError('uncertain ego lane')
  xs = np.linspace(0.0, min(35.0, max(10.0, speed * 2)), 12)
  left, right = sample(lines[1], xs), sample(lines[2], xs)
  path = sample(snapshot['path'], xs)
  widths = right - left
  if np.any(widths < 2.8) or np.any(widths > 4.5):
    raise ValueError('narrow or implausible lane')
  half = cfg.vehicle_width_m / 2 + cfg.line_margin_m
  lower = max(-cfg.max_offset_m, float(np.max(left + half - path)))
  upper = min(cfg.max_offset_m, float(np.min(right - half - path)))
  if lower > 0 or upper < 0:
    raise ValueError('baseline path lacks margin')
  return xs, lower, upper


def roadside_target(snapshot, cfg, xs):
  """Require positive right-edge AND left-lane evidence, not missing lines alone."""
  p, lines = snapshot['lane_probs'], snapshot['lane_lines']
  if p[0] < 0.6 or p[3] >= 0.3:
    return 0.0, None, 'ambiguous outer lanes'
  edges, stds = snapshot['road_edges'], snapshot['edge_stds']
  if len(edges) != 2 or len(stds) != 2 or not math.isfinite(stds[1]) or not 0 <= stds[1] <= 0.25:
    return 0.0, None, 'uncertain right edge'
  left_width = sample(lines[1], xs) - sample(lines[0], xs)
  right_gap = sample(edges[1], xs) - sample(lines[2], xs)
  if np.any(left_width < 2.5) or np.any(left_width > 4.5) or np.any(right_gap < 0) or np.any(right_gap > 1.5):
    return 0.0, None, 'rightmost geometry not confirmed'
  return -cfg.max_offset_m, 'roadside', 'right edge and left lane confirmed'


def vehicle_target(snapshot, cfg, observations):
  """Front-visible objects only. A class label is not a physical size measurement."""
  if not snapshot.get('perception_valid', False):
    return 0.0, None, 'perception unavailable'
  left_seen, right_seen, candidates = False, False, []
  for obj in observations:
    # Reject the whole scene if a road actor cannot be located. It may occupy the destination side.
    if not obj.get('geometry_valid', False):
      return 0.0, None, 'unlocated or truncated actor'
    x, lo, hi, conf = (float(obj[k]) for k in ('x_m', 'y_min_m', 'y_max_m', 'confidence'))
    if not all(math.isfinite(v) for v in (x, lo, hi, conf)) or lo > hi or not 0 <= conf <= 1:
      return 0.0, None, 'malformed actor'
    if not 4 <= x <= 35:
      continue
    left = float(sample(snapshot['lane_lines'][1], [x])[0])
    right = float(sample(snapshot['lane_lines'][2], [x])[0])
    # Boxes are enlarged laterally by perception.py to represent projection uncertainty.
    if hi < left and left - hi < 4.5:
      side = 'left'
      left_seen = True
      gap = left - hi
    elif lo > right and lo - right < 4.5:
      side = 'right'
      right_seen = True
      gap = lo - right
    elif hi >= left and lo <= right:
      return 0.0, None, 'actor intersects ego lane'
    else:
      continue
    track = obj.get('track_id')
    if obj['label'] in ('truck', 'bus') and conf >= 0.65 and isinstance(track, int) and track >= 0 and gap <= 2.0:
      candidates.append((x, side, track))
  if left_seen and right_seen:
    return 0.0, None, 'actors on both sides'
  if not candidates:
    return 0.0, None, 'no qualified large-vehicle track'
  _, side, track = min(candidates)
  return (cfg.max_offset_m if side == 'left' else -cfg.max_offset_m), f'{side}:{track}', f'large vehicle {side}'


class OffsetObserver:
  """Stateful replay policy. Its result intentionally has no actuation contract."""
  def __init__(self, cfg=None, mode='vehicles'):
    if mode not in ('roadside', 'vehicles'):
      raise ValueError('mode must be roadside or vehicles')
    self.cfg, self.mode = cfg or Config(), mode
    self.last_t = None
    self.key = None
    self.since = 0.0
    self.samples = 0
    self.offset = 0.0

  def update(self, snapshot, observations=()):
    reason, target, dt = 'invalid input', 0.0, 0.0
    reset = False
    try:
      t = float(snapshot['t'])
      if not math.isfinite(t):
        raise ValueError('nonfinite timestamp')
      if self.last_t is not None:
        dt = t - self.last_t
        if not 0 < dt <= self.cfg.max_gap_s:
          self.offset, self.key, self.samples = 0.0, None, 0
          reset = True
          raise ValueError('repeated, reversed or missing frames')
      self.last_t = t
      xs, lower, upper = geometry(snapshot, self.cfg)
      if self.mode == 'roadside':
        target, key, reason = roadside_target(snapshot, self.cfg, xs)
      else:
        target, key, reason = vehicle_target(snapshot, self.cfg, observations)
      target = float(np.clip(target, lower, upper))
      if key is None or target == 0:
        self.key, self.samples = None, 0
      elif key != self.key:
        self.key, self.since, self.samples = key, t, 1
        target = 0.0
        reason = 'confirming ' + reason
      else:
        self.samples += 1
        if t - self.since < self.cfg.confirm_s or self.samples < 4:
          target = 0.0
          reason = 'confirming ' + reason
      # Do not swing directly from one side to the other.
      if target * self.offset < 0:
        target = 0.0
        reason = 'returning to center before opposite offset'
      step = self.cfg.rate_mps * dt
      self.offset += float(np.clip(target - self.offset, -step, step))
      self.offset = float(np.clip(self.offset, lower, upper))
    except (KeyError, TypeError, ValueError, IndexError, OverflowError) as e:
      reason = str(e)
      self.offset, self.key, self.samples = 0.0, None, 0
      if reset:
        self.last_t = float(snapshot['t'])
    return {
      'mode': self.mode, 'target_offset_m': target if self.key is not None else 0.0,
      'candidate_offset_m': self.offset, 'reason': reason,
      'applied_offset_m': 0.0, 'control_eligible': False, 'scope': 'offline_shadow_only',
    }
