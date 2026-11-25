import math
from types import SimpleNamespace

import pytest

from openpilot.selfdrive.controls.lib.curve_centering import CurveCentering
from openpilot.selfdrive.modeld.constants import ModelConstants


def curve_model(curvature=0.004, inward=0.4, width=3.5, lane_curvature=None):
  # The model points right in positive y. Its reference path starts at the camera.
  xs = list(ModelConstants.X_IDXS)
  sign = math.copysign(1, curvature)
  road_curvature = curvature if lane_curvature is None else lane_curvature
  center = [0.5 * road_curvature * x**2 - sign * inward for x in xs]
  lines = [SimpleNamespace(x=xs.copy(), y=[y + multiplier * width for y in center])
           for multiplier in (-1.5, -0.5, 0.5, 1.5)]
  return SimpleNamespace(frameId=0, action=SimpleNamespace(desiredCurvature=curvature),
                         position=SimpleNamespace(x=xs, y=[0.5 * curvature * x**2 for x in xs]),
                         laneLines=lines, laneLineProbs=[0.0, 0.99, 0.99, 0.0], laneLineStds=[1.0, 0.05, 0.05, 1.0])


def responses(helper, model, speed=15.0, frames=40):
  result = []
  for _ in range(frames):
    model.frameId += 1
    result.append(helper.update(model, speed))
  return result


@pytest.mark.parametrize('speed', [10.0, 15.0, 30.0])
def test_mirrored_bends_trim_the_request_equally_within_acceleration_and_jerk_limits(speed):
  right = responses(CurveCentering(), curve_model(), speed)
  left = responses(CurveCentering(), curve_model(curvature=-0.004), speed)
  assert left == pytest.approx([-delta for delta in right])
  assert right[:3] == [0.0] * 3
  assert min(right) < 0.0
  assert all(-0.2 * 0.004 <= delta <= 0.0 for delta in right)
  assert all(abs(delta) * speed**2 <= 0.15 + 1e-9 for delta in right)
  assert all(0.0 <= (previous - current) * speed**2 <= 0.15 / 20 + 1e-9
             for previous, current in zip(right, right[1:], strict=False))


@pytest.mark.parametrize('inward', [-0.40, 0.0, 0.115])
def test_centered_outer_and_small_inner_offsets_leave_the_model_request_alone(inward):
  assert responses(CurveCentering(), curve_model(inward=inward)) == [0.0] * 40


def test_marginal_inward_error_cannot_command_past_the_lane_center():
  model = curve_model(inward=0.125)
  result = responses(CurveCentering(), model, speed=15.0)
  assert min(result) < 0.0
  # At 15 m/s the helper samples 9, 18 and 27 m ahead. Only the 5 mm above the deadband is available.
  for distance in (9, 18, 27):
    assert all(0.0 <= -0.5 * delta * distance**2 <= 0.005 + 1e-12 for delta in result)


def assert_rejected_after_active(model, speed=15.0):
  helper = CurveCentering()
  valid = curve_model()
  assert responses(helper, valid)[-1] < 0.0
  assert responses(helper, model, speed=speed, frames=6) == [0.0] * 6
  assert responses(helper, valid, frames=3) == [0.0] * 3
  assert responses(helper, valid)[-1] < 0.0


@pytest.mark.parametrize(('field', 'side', 'value'), [
  ('laneLineProbs', 1, 0.79), ('laneLineProbs', 2, 0.79), ('laneLineProbs', 1, math.nan),
  ('laneLineStds', 1, 0.21), ('laneLineStds', 2, math.inf),
])
def test_uncertain_boundaries_drop_the_correction(field, side, value):
  model = curve_model()
  getattr(model, field)[side] = value
  assert_rejected_after_active(model)


@pytest.mark.parametrize('kwargs', [
  {'width': 5.0}, {'width': 2.0}, {'width': -3.5}, {'inward': 2.0},
  {'curvature': 0.0}, {'curvature': math.nan}, {'lane_curvature': -0.004},
])
def test_bad_width_boundaries_on_one_side_and_inconsistent_turns_are_rejected(kwargs):
  assert_rejected_after_active(curve_model(**kwargs))


@pytest.mark.parametrize('speed', [3.0, math.nan])
def test_unusable_speed_discards_the_previous_correction(speed):
  assert_rejected_after_active(curve_model(), speed)


@pytest.mark.parametrize('geometry', ['missing', 'short', 'duplicate_x', 'nonfinite_line', 'nonfinite_path'])
def test_invalid_coordinate_grids_are_rejected(geometry):
  model = curve_model()
  line = model.laneLines[1]
  if geometry == 'missing':
    model.laneLines = model.laneLines[:2]
  elif geometry == 'short':
    line.x, line.y = line.x[:3], line.y[:3]
  elif geometry == 'duplicate_x':
    line.x[5] = line.x[4]
  elif geometry == 'nonfinite_line':
    line.x[0] = math.nan
  else:
    model.position.y[0] = math.nan
  assert_rejected_after_active(model)


def test_an_upcoming_countercurve_cancels_while_the_near_geometry_and_model_still_turn_right():
  model = curve_model()
  for line in model.laneLines:
    line.y = [y - 0.012 * max(x - 11, 0)**2 for x, y in zip(line.x, line.y, strict=True)]
  assert_rejected_after_active(model)


def test_diverging_lines_are_rejected_even_while_each_sample_is_a_normal_width():
  model = curve_model()
  right = model.laneLines[2]
  right.y = [y + min(0.8, x * 0.03) for x, y in zip(right.x, right.y, strict=True)]
  assert_rejected_after_active(model)


def test_approaching_the_center_and_reversing_direction_drop_the_previous_correction():
  helper = CurveCentering()
  right = curve_model()
  assert responses(helper, right)[-1] < 0.0
  # A shrinking margin must take effect immediately, even while the sign stays unchanged.
  small = helper.update(curve_model(inward=0.125), 15.0)
  assert 0.0 < -0.5 * small * 27**2 <= 0.005 + 1e-12
  assert helper.update(curve_model(inward=0.0), 15.0) == 0.0
  assert responses(helper, right)[-1] < 0.0
  left = responses(helper, curve_model(curvature=-0.004))
  assert left[:3] == [0.0] * 3
  assert all(delta >= 0.0 for delta in left)
  assert left[-1] > 0.0
  helper.reset()
  assert responses(helper, right, frames=3) == [0.0] * 3


@pytest.mark.parametrize('side', [-1, 1])
def test_outer_ego_position_vetoes_an_inward_future_path_in_either_bend(side):
  model = curve_model(curvature=side * 0.004, inward=-0.3)
  model.position.y = [y + side * 0.72 * min(1.0, x / 8.0) for x, y in zip(model.position.x, model.position.y, strict=True)]
  assert_rejected_after_active(model)


@pytest.mark.parametrize('side', [-1, 1])
def test_centered_ego_can_trim_a_reliably_inward_future_path(side):
  model = curve_model(curvature=side * 0.004, inward=0.0)
  model.position.y = [y + side * 0.4 * min(1.0, x / 8.0) for x, y in zip(model.position.x, model.position.y, strict=True)]
  assert side * responses(CurveCentering(), model)[-1] < 0.0
