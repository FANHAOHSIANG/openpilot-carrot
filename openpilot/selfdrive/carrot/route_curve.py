"""Navigation geometry matched to the near model path; a speed ceiling only.

Coordinates are WGS84 (longitude, latitude). No destination inference, route
service calls or mixing of navigation owners happens here. Missing geometry
cannot produce a preview. Control quantities are SI until the kph boundary.
"""
from collections import deque
from dataclasses import dataclass
import math

import numpy as np

from openpilot.selfdrive.carrot.curve_speed import (
  APPROACH_DECEL, APPROACH_JERK, NO_LIMIT_KPH, RESPONSE_TIME, TARGET_LAT_ACCEL,
  GEOMETRY_MIN_SPAN, GEOMETRY_RELEASE_WINDOW, RELEASE_RATE_KPH,
)

METRES_PER_DEGREE = math.pi * 6371000.0 / 180.0
PREVIEW_METRES = 500.0
SAMPLE_METRES = 5.0
SHORT_REVERSAL_METRES = 40.0
SHORT_REVERSAL_MIN_TURN = math.radians(5.0)
SHORT_REVERSAL_MAX_NET_TURN = math.radians(12.0)
SHORT_REVERSAL_MAX_OFFSET = 5.0
POSITION_MAX_AGE = 1.5
MODEL_MAX_AGE = 0.3
CONFIRM_SECONDS = 0.3
RELEASE_KPH_PER_SECOND = 3.6


def _short_lateral_reversals(relative):
  """Mask curvature windows that span a small lateral kink in a mostly straight road."""
  edges = np.diff(relative, axis=0)
  headings = np.unwrap(np.arctan2(edges[:, 1], edges[:, 0]))
  turns = np.diff(headings)
  turns[np.abs(turns) < math.radians(0.05)] = 0.
  # Split into contiguous changes in heading so a vertex straddling two
  # resampled edges has the same sign and magnitude as the original turn.
  signs = np.sign(turns)
  for i in range(1, len(signs)):
    if signs[i] == 0:
      signs[i] = signs[i - 1]
  starts = np.r_[0, np.flatnonzero(signs[1:] != signs[:-1]) + 1]
  ends = np.r_[starts[1:], len(turns)]
  corners = [(int(start), int(start + np.flatnonzero(turns[start:end])[-1]), float(np.sum(turns[start:end])))
             for start, end in zip(starts, ends, strict=True)
             if abs(np.sum(turns[start:end])) >= SHORT_REVERSAL_MIN_TURN]
  isolated = [(i, i, turns[i]) for i in np.flatnonzero(np.abs(turns) >= SHORT_REVERSAL_MIN_TURN)]
  rejected = np.zeros(len(relative), dtype=bool)
  for changes in (corners, isolated):
    for (first, _, first_turn), (_, last, last_turn) in zip(changes[:-1], changes[1:], strict=True):
      if ((last - first) * SAMPLE_METRES > SHORT_REVERSAL_METRES
          or first_turn * last_turn >= 0
          or abs(headings[last + 1] - headings[first]) > SHORT_REVERSAL_MAX_NET_TURN):
        continue
      # Measure excursion from the incoming edge, including any lateral shift.
      incoming = edges[first] / np.linalg.norm(edges[first])
      excursion = relative[first + 1:last + 3] - relative[first + 1]
      offset = excursion[:, 0] * incoming[1] - excursion[:, 1] * incoming[0]
      if np.max(np.abs(offset)) <= SHORT_REVERSAL_MAX_OFFSET:
        # The three-point curvature and its median together see +/-15 m.
        rejected[max(0, first - 1):last + 5] = True
  return rejected


def osm_bend_directions(relative, distances, centers, curvature, model_x, model_y, lateral_offset):
  """Corroborate each candidate using a forward 30 m window at the bend."""
  directions = np.zeros(len(centers))
  invalid = ~np.isfinite(model_x) | ~np.isfinite(model_y)
  invalid[1:] |= np.diff(model_x) <= 0.
  stop = np.flatnonzero(invalid)
  if len(stop):
    model_x, model_y = model_x[:stop[0]], model_y[:stop[0]]
  if len(model_x) < 2:
    return directions

  half_window = 3 * SAMPLE_METRES
  window = np.maximum(0., centers - half_window)[:, None] + [0., half_window, 2 * half_window]
  x = np.interp(window, distances, relative[:, 0])
  y = np.interp(window, distances, relative[:, 1])
  dx = np.diff(x, axis=1)
  map_turn = np.diff(np.arctan2(np.diff(y, axis=1), dx), axis=1)[:, 0]
  required_turn = .5 * curvature * half_window
  eligible = ((window[:, -1] <= distances[-1]) & np.all(dx > 0., axis=1)
              & (np.abs(map_turn) >= required_turn))
  corroborated = np.zeros_like(eligible)
  # A distant vision prediction can start bending before the mapped road does.
  # Allow up to one forward comparison window of longitudinal alignment while
  # retaining lateral, direction and curvature agreement at three points.
  for shift in (0., half_window, 2 * half_window):
    sample_x = x - shift
    model_at_bend = np.interp(sample_x, model_x, model_y)
    model_turn = np.diff(np.arctan2(np.diff(model_at_bend, axis=1), dx), axis=1)[:, 0]
    corroborated |= (eligible & (sample_x[:, 0] >= model_x[0] - SAMPLE_METRES / 2)
                     & (sample_x[:, -1] <= model_x[-1])
                     & np.all(np.abs(y - model_at_bend - lateral_offset) <= 3. + .04 * x, axis=1)
                     & (map_turn * model_turn > 0.) & (np.abs(model_turn) >= required_turn))
  directions[corroborated] = np.sign(map_turn[corroborated])
  return directions


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
    self.speed_from_osm = False
    self.osm_bends = {}
    self.osm_progress_offset = 0.
    self.osm_limit_bend = None
    self.release_geometry = deque()

  def _withdraw_osm_speed(self):
    if self.speed_from_osm:
      self.speed = NO_LIMIT_KPH
      self.speed_from_osm = False
      self.osm_limit_bend = None
      self.missing_since = None
      self.release_geometry.clear()

  def _withdraw_osm(self):
    self.osm_bends.clear()
    self._withdraw_osm_speed()

  def set_route(self, points, route_id):
    if route_id == self.route_id:
      return
    self.release_geometry.clear()
    old_id, old_points = self.route_id, self.points
    old_progress, old_arc = self.progress, getattr(self, 'arc', ())
    old_state = (self.match_time, self.confirm_since, self.confirm_frames, self.last_model_time)
    self.route_id = route_id
    self.points = ()
    self.route = np.empty((0, 2))
    self.progress = self.match_time = self.confirm_since = self.last_model_time = None
    self.confirm_frames = 0
    same_corridor = False
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
            self.osm_progress_offset += old_progress - self.progress
            same_corridor = True
            break
    except (TypeError, ValueError, IndexError):
      return
    finally:
      if not same_corridor:
        self.osm_progress_offset = 0.
        self._withdraw_osm()

  def _confirmed_osm_bends(self, stations, directions, now):
    # Track all corroborated parts of the bend. The tightest point moves as
    # the 5 m route samples move with the car, even on one continuous ramp.
    sections = np.floor((stations + self.osm_progress_offset) / (2 * SAMPLE_METRES)).astype(int)
    keys = [(section, direction) if direction else None for section, direction in zip(sections, directions, strict=True)]
    self.osm_bends = {key: evidence for key, evidence in self.osm_bends.items() if now - evidence[1] <= GEOMETRY_MIN_SPAN}
    confirmed = set()
    for key in set(keys) - {None}:
      first, _, frames = self.osm_bends.get(key, (now, now, 0))
      self.osm_bends[key] = first, now, frames + 1
      if now - first >= CONFIRM_SECONDS - 1e-9 and frames + 1 >= 4:
        confirmed.add(key)
    return keys, confirmed

  def atc_turn_speed(self, result, turn, distance):
    """Estimate a ceiling only for a dense, matched route at the current TBT."""
    confirmed_repeat = (result.reason == "repeated_model" and self.confirm_frames >= 4
                        and self.confirm_since is not None and self.match_time - self.confirm_since >= CONFIRM_SECONDS - 1e-9)
    if (result.reason != "matched" and not confirmed_repeat) or turn not in (1, 2) or not 5.0 <= distance <= 140.0:
      return None
    progress = self.progress
    start, end = distance - 12.0, distance + 30.0
    if progress + start < 0 or progress + end > self.arc[-1]:
      return None
    edges = (self.arc[:-1] < progress + end) & (self.arc[1:] > progress + start)
    if np.any(self.lengths[edges] > 12.0):
      return None

    sample = progress + np.linspace(start, end, 22)
    xy = np.column_stack([np.interp(sample, self.arc, self.route[:, i]) for i in range(2)])
    chords = xy[2:] - xy[:-2]
    heading = np.unwrap(np.arctan2(chords[:, 1], chords[:, 0]))
    changes = np.diff(heading)
    # XY is east/north, so positive rotation is left.
    signed = changes * (1 if turn == 1 else -1)
    if np.sum(signed) < math.radians(22) or np.sum(np.maximum(-signed, 0)) > math.radians(12):
      return None
    # Require the measured bend to be bracketed by the approach and exit.
    if np.max(np.abs(changes[:2])) > math.radians(3) or np.max(np.abs(changes[-2:])) > math.radians(3):
      return None
    peak = int(np.argmax(np.abs(changes)))
    if not distance - 6.0 <= sample[peak + 1] + 1.0 - progress <= distance + 18.0:
      return None
    peak_curvature = abs(float(changes[peak])) / 2.0
    if peak_curvature <= 0.0:
      return None
    return min(35.0, 3.6 * math.sqrt(1.3 / peak_curvature))

  def _invalid(self, reason, now, dt):
    self.confirm_since = None
    self.confirm_frames = 0
    return self._unconfirmed(reason, now, dt)

  def _unconfirmed(self, reason, now, dt):
    if reason == "repeated_model" and self.speed_from_osm:
      return RouteCurveResult(self.speed, reason)
    if reason in ("bend_confirming", "bend_unconfirmed"):
      self._withdraw_osm_speed()
    elif reason != "repeated_model":
      self._withdraw_osm()
    self.release_geometry.clear()
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
      self._withdraw_osm()
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
      full_mx, full_my = np.asarray(model.position.x, dtype=float), np.asarray(model.position.y, dtype=float)
      mx, my = full_mx, full_my
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
    osm = isinstance(self.route_id, tuple) and self.route_id[:1] == ('osm',)
    if osm:
      directions = osm_bend_directions(relative, distances, curve_distances, curve, full_mx, full_my, lateral_offset)
    if isinstance(self.route_id, tuple) and self.route_id[:1] == ('nav',):
      # Near-path agreement cannot confirm a distant bend. Leave these local
      # map discontinuities to the independent vision curve speed estimate.
      curve[_short_lateral_reversals(relative)[3:-3][usable]] = 0.
    self.missing_since = None
    ratio = speed_ratio if 0.5 < speed_ratio <= 1.2 else 1.0
    budget = TARGET_LAT_ACCEL / float(np.clip(sensitivity, 0.5, 3.0))
    # Use the tighter possible lane radius, never a faster centreline cap.
    curve = curve / np.maximum(0.1, 1. - curve * max(0., min(7.2, lateral_allowance)))
    curve_ms = np.sqrt(budget / np.maximum(curve, 1e-9)) * float(np.clip(map_factor, 0.5, 3.0))
    curve_ms = np.maximum(curve_ms, max(5.0, lower_limit_kph) * ratio / 3.6)
    delay = RESPONSE_TIME + (max(0.0, a_ego) + APPROACH_DECEL) / (2 * APPROACH_JERK)
    approach = np.sqrt(curve_ms**2 + 2 * APPROACH_DECEL * np.maximum(0, curve_distances - v_ego * delay)) * 3.6 / ratio
    if osm:
      directions[approach >= NO_LIMIT_KPH] = 0.
      keys, confirmed = self._confirmed_osm_bends(s + curve_distances, directions, now)
      approach[[key not in confirmed for key in keys]] = NO_LIMIT_KPH
      if not np.any(approach < NO_LIMIT_KPH):
        return self._unconfirmed("bend_confirming" if np.any(directions) else "bend_unconfirmed", now, dt)
      if self.osm_limit_bend not in confirmed:
        self._withdraw_osm_speed()
    index = int(np.argmin(approach))
    target = min(NO_LIMIT_KPH, float(approach[index]))
    # Matching a road is not yet proof that a transient higher cap is an exit.
    # Require independent, fresh matched frames, using the same short evidence
    # window as vision. Keep loss/reacquisition on the slower fallback above.
    if self.release_geometry and now - self.release_geometry[-1][0] > GEOMETRY_MIN_SPAN:
      self.release_geometry.clear()
    self.release_geometry.append((now, target))
    while self.release_geometry and now - self.release_geometry[0][0] > GEOMETRY_RELEASE_WINDOW + 1e-9:
      self.release_geometry.popleft()
    confirmed_exit = len(self.release_geometry) >= 3 and now - self.release_geometry[0][0] >= GEOMETRY_MIN_SPAN - 1e-9
    if target <= self.speed:
      self.speed = target
      self.speed_from_osm = osm and target < NO_LIMIT_KPH
      self.osm_limit_bend = keys[index] if self.speed_from_osm else None
    elif confirmed_exit:
      # This only relaxes a speed ceiling. Existing turn_accel, cruise/lead
      # limits and MPC jerk control still determine the actual acceleration.
      confirmed_target = min(speed for _, speed in self.release_geometry)
      self.speed = max(self.speed, min(confirmed_target, self.speed + RELEASE_RATE_KPH * dt))
    return RouteCurveResult(self.speed, "matched", min(NO_LIMIT_KPH, float(curve_ms[index] * 3.6 / ratio)),
                            float(curve_distances[index]), match_error,
                            tuple(map(tuple, relative[distances >= 0])), tuple(distances[distances >= 0]), lateral_offset)
