import math

import pytest

from openpilot.tools.curve_centering.speed_feasibility import CurvatureConstraint, preview_speed_limit


def limit(points, **changes):
  args = {'requested_speed':30.0, 'lateral_budget':2.4, 'decel':2.0, 'latency':.3}
  args.update(changes)
  return preview_speed_limit(points, **args)


def test_current_curve_requires_feasible_speed():
  result = limit([CurvatureConstraint(0, .01)])
  assert result['speed_mps'] == pytest.approx(math.sqrt(2.4/.01))
  assert result['speed_mps'] < 18  # 64.8 km/h is infeasible under these assumptions.


def test_reaction_and_braking_distance_identity():
  result = limit([CurvatureConstraint(50, .01)])
  v = result['speed_mps']
  assert v*.3+(v*v-2.4/.01)/(2*2) == pytest.approx(50)


def test_more_latency_or_curvature_never_increases_allowed_speed():
  points = [CurvatureConstraint(50, .01)]
  assert limit(points, latency=1)['speed_mps'] < limit(points)['speed_mps']
  assert limit([CurvatureConstraint(50, .02)])['speed_mps'] < limit(points)['speed_mps']


def test_near_curve_never_requires_speed_below_its_cap():
  assert limit([CurvatureConstraint(1, .01)], latency=5)['speed_mps'] == pytest.approx(math.sqrt(240))


def test_straight_preview_does_not_raise_requested_speed():
  result = limit([CurvatureConstraint(0, 0), CurvatureConstraint(100, 0)])
  assert result['speed_mps'] == 30
  assert result['preview_end_m'] == 100


def test_denser_duplicate_constraint_does_not_repeat_latency():
  sparse = limit([CurvatureConstraint(50, .01)])
  dense = limit([CurvatureConstraint(50, .01), CurvatureConstraint(51, .01), CurvatureConstraint(52, .01)])
  assert sparse['speed_mps'] == dense['speed_mps']


@pytest.mark.parametrize('points', [[], [CurvatureConstraint(-1, .01)], [CurvatureConstraint(0, math.nan)],
                                    [CurvatureConstraint(1, 0), CurvatureConstraint(0, 0)]])
def test_invalid_preview(points):
  with pytest.raises(ValueError):
    limit(points)


@pytest.mark.parametrize('changes', [{'lateral_budget':0}, {'decel':0}, {'latency':-1}, {'requested_speed':math.inf}])
def test_invalid_assumptions(changes):
  with pytest.raises(ValueError):
    limit([CurvatureConstraint(0, .01)], **changes)
