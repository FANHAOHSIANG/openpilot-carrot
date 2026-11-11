import math
from types import SimpleNamespace

import numpy as np
import pytest

from openpilot.selfdrive.carrot.route_curve import METRES_PER_DEGREE, RouteCurveSpeed


def lonlat(xy):
  return np.asarray(xy) / [METRES_PER_DEGREE * math.cos(math.radians(25)), METRES_PER_DEGREE] + [121, 25]


def road(start=200, radius=80, direction=1):
  straight = np.column_stack([np.arange(0, start, 5), np.zeros(len(np.arange(0, start, 5)))])
  angle = np.linspace(0, math.pi / 2, 41)
  turn = np.column_stack([start + radius * np.sin(angle), direction * radius * (1 - np.cos(angle))])
  exit_road = np.column_stack([np.full(40, start + radius), direction * (radius + np.arange(5, 205, 5))])
  return np.vstack([straight, turn, exit_road])


def model_for(xy, position=(0, 0), heading=90):
  angle = math.radians(heading)
  delta = np.asarray(xy) - position
  local = np.column_stack([delta @ [math.sin(angle), math.cos(angle)], delta @ [math.cos(angle), -math.sin(angle)]])
  ahead = local[(local[:, 0] >= 0) & (local[:, 0] <= 70)]
  # Test fixture spans only the near forward path; no far-map data enters vision.
  x = np.linspace(0, min(60, ahead[-1, 0]), 33)
  return SimpleNamespace(position=SimpleNamespace(x=x, y=np.interp(x, ahead[:, 0], ahead[:, 1])))


def run(tracker, xy, *, position=(0, 0), heading=90, start_time=10, frames=9, **kwargs):
  options = {'position': lonlat(position), 'heading': heading, 'model': model_for(xy, position, heading), 'v_ego': 25.}
  options.update(kwargs)
  results = []
  for i in range(frames):
    now = start_time + i * .05
    options.setdefault('position_time', now)
    options.setdefault('model_time', now)
    results.append(tracker.update(now=now, **options))
    if 'position_time' not in kwargs:
      options.pop('position_time')
    if 'model_time' not in kwargs:
      options.pop('model_time')
  return results


@pytest.mark.parametrize('direction', [-1, 1])
def test_route_sees_curve_beyond_visual_horizon_and_has_distance_envelope(direction):
  xy = road(direction=direction)
  tracker = RouteCurveSpeed()
  tracker.set_route(lonlat(xy), 1)
  result = run(tracker, xy)[-1]
  assert result.reason == 'matched'
  assert 180 < result.distance < 250  # beyond the current 180 m vision cap
  assert 40 < result.curve_kph < 50
  assert result.curve_kph < result.speed_kph < 90
  # Current cap can reach the curve target under 1 m/s2 with response allowance.
  assert ((result.speed_kph / 3.6)**2 - (result.curve_kph / 3.6)**2) / (2 * result.distance) <= 1.0


def test_tightens_as_vehicle_approaches_and_keeps_cluster_units():
  xy = road()
  results = []
  for x in (0, 50, 100, 150):
    tracker = RouteCurveSpeed()
    tracker.set_route(lonlat(xy), 1)
    results.append(run(tracker, xy, position=(x, 0))[-1])
  assert all(r.reason == 'matched' for r in results)
  assert all(a.speed_kph > b.speed_kph for a, b in zip(results, results[1:], strict=False))
  tracker = RouteCurveSpeed()
  tracker.set_route(lonlat(xy), 1)
  scaled = run(tracker, xy, speed_ratio=.9)[-1]
  assert scaled.speed_kph * .9 == pytest.approx(results[0].speed_kph)


@pytest.mark.parametrize('kind,reason', [
  ('gps', 'stale_position'), ('model_age', 'stale_model'), ('heading', 'off_route'),
  ('lateral', 'model_mismatch'), ('fork', 'model_mismatch'), ('jump', 'position_jump'),
  ('nan_model', 'invalid_model'), ('missing_route', 'no_route'),
])
def test_rejects_invalid_inputs_without_false_new_braking(kind, reason):
  xy = road()
  tracker = RouteCurveSpeed()
  tracker.set_route(lonlat(xy), 1)
  options = {}
  if kind == 'gps':
    options['position_time'] = 1.
  elif kind == 'model_age':
    options['model_time'] = 1.
  elif kind == 'heading':
    options['heading'] = 270
    options['model'] = model_for(xy)
  elif kind == 'lateral':
    options['position'] = (0, 7)
    options['model'] = model_for(xy)
  elif kind == 'fork':
    options['model'] = model_for(xy)
    options['model'].position.y = np.linspace(0, 16, 33)
  elif kind == 'jump':
    run(tracker, xy)
    options['position'] = (80, 0)
    options['start_time'] = 10.45
  elif kind == 'nan_model':
    options['model'] = model_for(xy)
    options['model'].position.y[10] = math.nan
  else:
    tracker.set_route([], 2)
  before = tracker.speed
  result = run(tracker, xy, **options)[-1]
  assert result.reason == reason
  assert result.speed_kph >= before


def test_sparse_or_malformed_routes_are_not_interpreted_as_curves():
  xy = road()
  for points in ([], [(121, 25)], [[math.nan, 25]] * 3, [[500, 25]] * 3,
                 lonlat([(0, 0), (150, 0), (150, 150)]), ['bad']):
    tracker = RouteCurveSpeed()
    tracker.set_route(points, 1)
    result = run(tracker, xy)[-1]
    assert result.speed_kph == 250
    assert result.reason in ('no_route', 'coarse_route')


def test_repeated_model_cannot_confirm_or_release():
  xy = road()
  tracker = RouteCurveSpeed()
  tracker.set_route(lonlat(xy), 1)
  results = run(tracker, xy, model_time=10.)
  assert all(r.speed_kph == 250 for r in results)
  assert results[-1].reason == 'stale_model'


def test_unneeded_far_model_tail_does_not_discard_near_agreement():
  xy = road()
  model = model_for(xy)
  model.position.x[-2:] = math.nan
  model.position.y[-2:] = math.nan
  tracker = RouteCurveSpeed()
  tracker.set_route(lonlat(xy), 1)
  result = run(tracker, xy, model=model)[-1]
  assert result.reason == 'matched'


def test_map_factor_does_not_manufacture_limit_on_straight_road():
  xy = np.column_stack([np.arange(0, 605, 5), np.zeros(121)])
  tracker = RouteCurveSpeed()
  tracker.set_route(lonlat(xy), 1)
  assert run(tracker, xy, map_factor=.5)[-1].speed_kph == 250


def test_route_change_and_loss_release_gradually_instead_of_holding_old_curve():
  xy = road(start=40)
  tracker = RouteCurveSpeed()
  tracker.set_route(lonlat(xy), 1)
  first = run(tracker, xy)[-1]
  assert first.speed_kph < 60
  tracker.set_route([], 2)
  results = run(tracker, xy, start_time=10.45, frames=30)
  assert results[0].speed_kph == first.speed_kph
  assert results[-1].speed_kph > first.speed_kph
  assert max(np.diff([r.speed_kph for r in results])) <= .180001
  assert tracker.progress is None


def test_confirmed_opening_curve_releases_without_jumping_and_next_bend_tightens():
  xy = road(start=40)
  tracker = RouteCurveSpeed()
  tracker.set_route(lonlat(xy), 1)
  first = run(tracker, xy)[-1]
  straight = np.column_stack([np.arange(0, 605, 5), np.zeros(121)])
  tracker.set_route(lonlat(straight), 2)
  results = run(tracker, straight, start_time=10.45, frames=40)
  assert results[-1].speed_kph > first.speed_kph
  assert max(np.diff([r.speed_kph for r in results])) <= .180001
  tight = road(start=25, radius=35)
  tracker.set_route(lonlat(tight), 3)
  result = run(tracker, tight, start_time=12.5)[-1]
  assert result.reason == 'matched'
  assert result.speed_kph < first.speed_kph


def test_loop_ambiguity_does_not_select_nearest_unrelated_leg():
  xy = np.array([(0, 0), (100, 0), (100, 50), (-30, 50), (-30, 2), (100, 2)])
  tracker = RouteCurveSpeed()
  tracker.set_route(lonlat(xy), 1)
  result = run(tracker, road(), position=(20, 0))[-1]
  assert result.reason == 'ambiguous_route'
  assert result.speed_kph == 250


@pytest.mark.parametrize('direction', [-1, 1])
def test_cardinal_frame_agreement_uses_model_right_positive(direction):
  # Driving north: east is on the right. This fixture uses the documented
  # calibrated frame directly rather than the test coordinate helper.
  y = np.arange(0, 405, 5.)
  x = direction * .002 * y**2
  xy = np.column_stack([x, y])
  mx = np.linspace(0, 60, 33)
  model = SimpleNamespace(position=SimpleNamespace(x=mx, y=direction * .002 * mx**2))
  tracker = RouteCurveSpeed()
  tracker.set_route(lonlat(xy), 1)
  result = run(tracker, xy, heading=0, model=model)[-1]
  assert result.reason == 'matched'
  assert np.sign(result.points[8][1]) == direction
  model.position.y *= -1
  result = run(tracker, xy, heading=0, model=model, start_time=10.45)[-1]
  assert result.reason == 'model_mismatch'


def test_vehicle_progress_through_opening_curve_gradually_releases():
  # Continuous road: 80 m radius, easing to 250 m, then straight.
  ds = 2.0
  s = np.arange(0, 802, ds)
  k = np.where(s < 80, 1 / 80, np.where(s < 160, np.interp(s, [80, 160], [1 / 80, 1 / 250]), 0))
  theta = np.cumsum(k * ds)
  xy = np.column_stack([np.cumsum(np.cos(theta) * ds), np.cumsum(np.sin(theta) * ds)])
  tracker = RouteCurveSpeed()
  tracker.set_route(lonlat(xy), 1)
  speeds = []
  reasons = []
  for i in range(500):
    progress = 20 + i * .5
    position = tuple(np.interp(progress, s, xy[:, axis]) for axis in range(2))
    direction = np.interp(progress, s, theta)
    heading = 90 - math.degrees(direction)
    near = xy[(s >= progress) & (s <= progress + 90)]
    model = model_for(near, position, heading)
    result = tracker.update(now=10 + i * .05, position=lonlat(position), heading=heading,
                            position_time=10 + i * .05, model=model, model_time=10 + i * .05, v_ego=10.)
    speeds.append(result.speed_kph)
    reasons.append(result.reason)
  assert set(reasons[10:]) == {'matched'}
  assert speeds[40] < 50
  assert speeds[-1] > speeds[40] + 20
  assert max(np.diff(speeds[10:])) <= .180001


def test_known_lane_width_accepts_translation_but_not_shape_or_excess_offset():
  xy = road()
  tracker = RouteCurveSpeed()
  tracker.set_route(lonlat(xy), 1)
  # Driving a lane offset from the motorway centreline, with the same near shape.
  result = run(tracker, xy, position=(0, 6.5), model=model_for(xy), lateral_allowance=7.2)[-1]
  assert result.reason == 'matched'
  assert abs(result.lateral_offset) == pytest.approx(6.5, abs=.01)
  baseline = RouteCurveSpeed()
  baseline.set_route(lonlat(xy), 1)
  assert result.speed_kph <= run(baseline, xy)[-1].speed_kph
  for offset, slope in [(7.8, 0.), (6.5, .15)]:
    tracker = RouteCurveSpeed()
    tracker.set_route(lonlat(xy), 1)
    model = model_for(xy)
    model.position.y = np.asarray(model.position.y) + slope * np.asarray(model.position.x)
    rejected = run(tracker, xy, position=(0, offset), model=model, lateral_allowance=7.2)[-1]
    assert rejected.reason == 'model_mismatch'
    assert rejected.match_error > 4.9


def test_lane_allowance_does_not_bypass_stale_model_or_position():
  xy = road()
  for overrides, reason in [({'model_time': 8.}, 'stale_model'), ({'position_time': 8.}, 'stale_position')]:
    tracker = RouteCurveSpeed()
    tracker.set_route(lonlat(xy), 1)
    assert run(tracker, xy, lateral_allowance=7.2, **overrides)[-1].reason == reason
