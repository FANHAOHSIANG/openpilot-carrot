"""Navigation geometry matched to the near model path; a speed ceiling only.

Coordinates are WGS84 (longitude, latitude). No destination inference, route
service calls or mixing of navigation owners happens here. Missing geometry
cannot produce a preview. Control quantities are SI until the kph boundary.
"""
from dataclasses import dataclass
import math

import numpy as np

from openpilot.selfdrive.carrot.curve_speed import (
  APPROACH_DECEL, APPROACH_JERK, NO_LIMIT_KPH, RESPONSE_TIME, TARGET_LAT_ACCEL,
)

METRES_PER_DEGREE = math.pi * 6371000.0 / 180.0
PREVIEW_METRES = 500.0
SAMPLE_METRES = 5.0
POSITION_MAX_AGE = 1.5
MODEL_MAX_AGE = 0.3
CONFIRM_SECONDS = 0.3
RELEASE_KPH_PER_SECOND = 3.6


@dataclass(frozen=True)
class RouteCurveResult:
  speed_kph: float = NO_LIMIT_KPH
  reason: str = "no_route"
  curve_kph: float = NO_LIMIT_KPH
  distance: float = 0.0
  match_error: float = 0.0
  points: tuple = ()
  distances: tuple = ()
  lateral_offset: float = 0.


class RouteCurveSpeed:
  def __init__(self):
    self.route_id = None
    self.route = np.empty((0, 2))
    self.points = ()
    self.progress = None
    self.match_time = None
    self.confirm_since = None
    self.confirm_frames = 0
    self.last_model_time = None
    self.last_time = None
    self.missing_since = None
    self.speed = NO_LIMIT_KPH

  def set_route(self, points, route_id):
    if route_id == self.route_id:
      return
    old_id, old_points = self.route_id, self.points
    old_progress, old_arc = self.progress, getattr(self, 'arc', ())
    old_state = (self.match_time, self.confirm_since, self.confirm_frames, self.last_model_time)
    self.route_id = route_id
    self.points = ()
    self.route = np.empty((0, 2))
    self.progress = self.match_time = self.confirm_since = self.last_model_time = None
    self.confirm_frames = 0
    try:
      points = np.asarray(points, dtype=float)
      if (points.ndim != 2 or points.shape[1] != 2 or not 3 <= len(points) <= 4096
          or not np.all(np.isfinite(points)) or np.any(np.abs(points[:, 0]) > 180)
          or np.any(np.abs(points[:, 1]) > 85)):
        return
      self.origin = points[0]
      self.scale = np.array([METRES_PER_DEGREE * math.cos(math.radians(self.origin[1])), METRES_PER_DEGREE])
      xy = (points - self.origin) * self.scale
      # Consecutive duplicate points carry no heading or curvature information.
      keep = np.r_[True, np.linalg.norm(np.diff(xy, axis=0), axis=1) > 0.1]
      xy = xy[keep]
      if len(xy) < 3:
        return
      self.points = tuple(map(tuple, points[keep]))
      self.route = xy
      self.delta = np.diff(xy, axis=0)
      self.lengths = np.linalg.norm(self.delta, axis=1)
      self.arc = np.r_[0.0, np.cumsum(self.lengths)]
      # A moving OSM window may trim only the already travelled prefix or add
      # geometry after the entire old forward suffix. Preserve evidence only
      # across exact, ordered edges, never a replacement fork or navigation owner.
      if (isinstance(old_id, tuple) and isinstance(route_id, tuple) and old_id[:1] == route_id[:1] == ('osm',)
          and old_progress is not None and len(old_points) >= 3):
        i = min(len(old_points) - 2, int(np.searchsorted(old_arc, old_progress, side='right') - 1))
        suffix = old_points[max(0, i):]
        for j in range(max(0, len(self.points) - len(suffix) + 1)):
          if self.points[j:j + len(suffix)] == suffix and old_arc[-1] - old_progress >= 60.:
            self.progress = float(self.arc[j] + old_progress - old_arc[max(0, i)])
            self.match_time, self.confirm_since, self.confirm_frames, self.last_model_time = old_state
            break
    except (TypeError, ValueError, IndexError):
      return

  def _invalid(self, reason, now, dt):
    self.confirm_since = None
    self.confirm_frames = 0
    return self._unconfirmed(reason, now, dt)

  def _unconfirmed(self, reason, now, dt):
    if self.missing_since is None:
      self.missing_since = now
    # Lost geometry is not proof of a straight road. Remove its old constraint
    # gradually; vision, lead, cruise and other ceilings remain downstream.
    if now - self.missing_since >= 0.35:
      self.speed = min(NO_LIMIT_KPH, self.speed + RELEASE_KPH_PER_SECOND * dt)
    return RouteCurveResult(self.speed, reason)

  def update(self, *, now, position, heading, position_time, model, model_time,
             v_ego, a_ego=0.0, speed_ratio=1.0, sensitivity=1.0,
             map_factor=1.0, lower_limit_kph=30.0, lateral_allowance=0.0):
    if not math.isfinite(now):
      return RouteCurveResult(self.speed, "invalid_time")
    dt = 0.0 if self.last_time is None else min(0.2, max(0.0, now - self.last_time))
    clock_reset = self.last_time is not None and now < self.last_time
    self.last_time = now
    def invalid(reason):
      return self._invalid(reason, now, dt)
    if clock_reset:
      self.progress = self.match_time = self.last_model_time = None
      self.missing_since = None
      return invalid("clock_reset")
    if len(self.route) < 3:
      return invalid("no_route")
    values = (*position, heading, position_time, model_time, v_ego, a_ego,
              speed_ratio, sensitivity, map_factor, lower_limit_kph, lateral_allowance)
    if not all(math.isfinite(v) for v in values) or not 2.0 <= v_ego <= 90 or sensitivity <= 0 or map_factor <= 0:
      return invalid("invalid_input")
    if not 0 <= now - position_time <= POSITION_MAX_AGE:
      return invalid("stale_position")
    if not 0 <= now - model_time <= MODEL_MAX_AGE:
      return invalid("stale_model")
    p = (np.asarray(position) - self.origin) * self.scale
    t = np.clip(np.sum((p - self.route[:-1]) * self.delta, axis=1) / self.lengths**2, 0, 1)
    projected = self.route[:-1] + t[:, None] * self.delta
    error = np.linalg.norm(projected - p, axis=1)
    progress = self.arc[:-1] + t * self.lengths
    angle = math.radians(heading)
    forward = np.array([math.sin(angle), math.cos(angle)])
    # Calibrated/model coordinates are forward, RIGHT, down.
    right = np.array([math.cos(angle), -math.sin(angle)])
    alignment = self.delta @ forward / self.lengths
    candidates = np.flatnonzero((error <= max(8., min(7.2, max(0., lateral_allowance)) + 2.)) & (alignment >= math.cos(math.radians(30))))
    if not len(candidates):
      return invalid("off_route")
    best = candidates[np.argmin(error[candidates])]
    # Distinct similarly close route legs at intersections/loops are ambiguous.
    if np.any((np.abs(progress[candidates] - progress[best]) > 30) & (error[candidates] <= error[best] + 3)):
      return invalid("ambiguous_route")
    s = float(progress[best])
    if self.progress is not None and now - self.match_time <= 2.0:
      advance = s - self.progress
      if advance < -5 or advance > v_ego * (now - self.match_time) + 15:
        return invalid("position_jump")
    if self.match_time is not None and now - self.match_time > 0.2:
      self.confirm_since = None
      self.confirm_frames = 0
    self.progress, self.match_time = s, now
    # Never calculate a turn by interpolating across a missing/coarse route leg.
    start = -min(15.0, math.floor(s / SAMPLE_METRES) * SAMPLE_METRES)
    distances = np.arange(start, min(PREVIEW_METRES, self.arc[-1] - s) + 0.01, SAMPLE_METRES)
    if len(distances) < 9:
      return invalid("short_route")
    xy = np.column_stack([np.interp(s + distances, self.arc, self.route[:, i]) for i in range(2)]) - p
    relative = np.column_stack([xy @ forward, xy @ right])
    lateral_offset = 0.
    try:
      mx, my = np.asarray(model.position.x, dtype=float), np.asarray(model.position.y, dtype=float)
      if len(mx) != 33 or len(my) != 33:
        return invalid("invalid_model")
      near = (relative[:, 0] >= 10) & (relative[:, 0] <= min(60, max(30, v_ego * 2.0))) & (distances <= 70)
      rx, ry = relative[near].T
      if len(rx) < 3 or np.any(np.diff(rx) <= 0):
        return invalid("short_model")
      reached = np.flatnonzero(mx >= rx[-1])
      if not len(reached):
        return invalid("short_model")
      end = int(reached[0]) + 1
      mx, my = mx[:end], my[:end]
      if not np.all(np.isfinite([mx, my])):
        return invalid("invalid_model")
      if len(mx) < 2 or np.any(np.diff(mx) <= 0):
        return invalid("short_model")
      difference = ry - np.interp(rx, mx, my)
      residual = np.abs(difference)
      match_error = float(np.max(residual))
      if np.any(residual > 3.0 + 0.04 * rx):
        # OSM's centreline is not a lane centre. Only a unique, explicitly
        # tagged divided motorway corridor may account for its carriageway
        # width. Do not rotate, fit slope or remove a wrong-fork shape.
        offset = float(np.median(difference))
        allowance = min(7.2, max(0., lateral_allowance))
        if not (allowance > 0 and abs(offset) <= allowance
                and np.all(np.abs(difference - offset) <= 1.5 + .01 * rx)):
          result = invalid("model_mismatch")
          return RouteCurveResult(result.speed_kph, result.reason, match_error=match_error)
        lateral_offset = offset
    except (AttributeError, ValueError, TypeError):
      return invalid("invalid_model")
    if self.last_model_time is None or model_time > self.last_model_time:
      self.last_model_time = model_time
      self.confirm_frames += 1
      if self.confirm_since is None:
        self.confirm_since = now
    else:
      return self._unconfirmed("repeated_model", now, dt)
    if now - self.confirm_since < CONFIRM_SECONDS - 1e-9 or self.confirm_frames < 4:
      return self._unconfirmed("confirming", now, dt)
    # Three-point circumcircle over +/-10 m. Its curvature belongs to the
    # middle point, not the end point or the original route origin.
    a, b, c = relative[:-4], relative[2:-2], relative[4:]
    ab, bc, ac = b - a, c - b, c - a
    denom = np.linalg.norm(ab, axis=1) * np.linalg.norm(bc, axis=1) * np.linalg.norm(ac, axis=1)
    curve = np.abs(2 * (ab[:, 0] * bc[:, 1] - ab[:, 1] * bc[:, 0]) / np.maximum(denom, 1e-6))
    # Median rejects an isolated map vertex without widening away an actual arc.
    curve = np.median(np.stack([curve[:-2], curve[1:-1], curve[2:]]), axis=0)
    curve_distances = distances[3:-3]
    usable = curve_distances >= 0
    for i in np.flatnonzero(self.lengths > 60):
      usable &= ~((s + curve_distances + 15 >= self.arc[i]) & (s + curve_distances - 15 <= self.arc[i + 1]))
    if not np.any(usable):
      # Near-path agreement is still valid evidence; sparse far-map geometry
      # cannot create a speed cap or erase that independent confirmation.
      near_straight = np.max(np.abs(np.diff(np.diff(ry)))) < .1 and np.ptp(ry) < 1.
      return self._unconfirmed("coarse_straight" if near_straight else "coarse_route", now, dt)
    curve, curve_distances = curve[usable], curve_distances[usable]
    self.missing_since = None
    ratio = speed_ratio if 0.5 < speed_ratio <= 1.2 else 1.0
    budget = TARGET_LAT_ACCEL / float(np.clip(sensitivity, 0.5, 3.0))
    # Use the tighter possible lane radius, never a faster centreline cap.
    curve = curve / np.maximum(0.1, 1. - curve * max(0., min(7.2, lateral_allowance)))
    curve_ms = np.sqrt(budget / np.maximum(curve, 1e-9)) * float(np.clip(map_factor, 0.5, 3.0))
    curve_ms = np.maximum(curve_ms, max(5.0, lower_limit_kph) * ratio / 3.6)
    delay = RESPONSE_TIME + (max(0.0, a_ego) + APPROACH_DECEL) / (2 * APPROACH_JERK)
    approach = np.sqrt(curve_ms**2 + 2 * APPROACH_DECEL * np.maximum(0, curve_distances - v_ego * delay)) * 3.6 / ratio
    index = int(np.argmin(approach))
    target = min(NO_LIMIT_KPH, float(approach[index]))
    self.speed = min(target, self.speed + RELEASE_KPH_PER_SECOND * dt)
    return RouteCurveResult(self.speed, "matched", min(NO_LIMIT_KPH, float(curve_ms[index] * 3.6 / ratio)),
                            float(curve_distances[index]), match_error,
                            tuple(map(tuple, relative[distances >= 0])), tuple(distances[distances >= 0]), lateral_offset)
