from copy import deepcopy
import math

import pytest

from openpilot.tools.curve_centering.uncertainty_shadow import GeometryBound, UncertaintyShadow, nearest_zero_error
from openpilot.tools.curve_centering.tests.test_centering_shadow import sample


def evidence(**changes):
  values = {'error_bound_m':0.2, 'preview_m':20.0, 'valid_from':0.0, 'valid_until':20.0, 'reference':'synthetic-test'}
  values.update(changes)
  return GeometryBound(**values)


@pytest.mark.parametrize('error, expected', [(-0.5, -0.3), (-0.2, 0), (0, 0), (0.2, 0), (0.5, 0.3)])
def test_interval_has_no_unsupported_direction(error, expected):
  assert nearest_zero_error(error, 0.2) == pytest.approx(expected)


@pytest.mark.parametrize('error, bound', [(math.nan, 0.2), (0.2, -0.1), (True, 0.2), (0.2, math.inf)])
def test_rejects_invalid_interval(error, bound):
  with pytest.raises(ValueError):
    nearest_zero_error(error, bound)


@pytest.mark.parametrize('changes', [{'error_bound_m':-1}, {'reference':''}, {'valid_until':-1}, {'preview_m':0}, {'valid_from':math.nan}])
def test_invalid_bound(changes):
  with pytest.raises(ValueError):
    evidence(**changes)


def test_absence_of_evidence_never_enters():
  shadow = UncertaintyShadow()
  for i in range(80):
    result = shadow.update(sample(i*.05))
    assert result['delta_accel'] == 0
    assert not result['active_candidate']


def test_interval_crossing_zero_has_no_correction():
  shadow = UncertaintyShadow()
  for i in range(80):
    result = shadow.update(sample(i*.05, .1), evidence())
    assert result['delta_accel'] == 0
  assert 'geometry_direction_uncertain' in result['reasons']


def test_correct_sign_bounded_gain_and_no_input_mutation():
  shadow = UncertaintyShadow(gain=.5)
  for i in range(80):
    row = sample(i*.05, .5)
    original = deepcopy(row)
    result = shadow.update(row, evidence())
    assert row == original
  assert result['robust_error_m'] == pytest.approx(.3)
  assert result['delta_accel'] == pytest.approx(-.25)
  assert result['relative_path_error_m'] == pytest.approx(.15)


@pytest.mark.parametrize('replacement', [None, evidence(valid_until=3), evidence(valid_from=10), evidence(preview_m=30)])
def test_evidence_loss_decays_and_reentry_waits(replacement):
  shadow = UncertaintyShadow()
  for i in range(81):
    previous = shadow.update(sample(i*.05), evidence())
  result = shadow.update(sample(4.05), replacement)
  assert abs(result['delta_accel']) < abs(previous['delta_accel'])
  assert abs(result['delta_accel']-previous['delta_accel']) <= .0125+1e-12
  assert not result['active_candidate']
  for i in range(19):
    assert not shadow.update(sample(4.1+i*.05), evidence())['active_candidate']


@pytest.mark.parametrize('changes', [{'driver_pressed':True}, {'desire':'laneChangeRight'}, {'lane_change_state':'preLaneChange'}])
def test_manual_and_maneuver_gates_retained(changes):
  shadow = UncertaintyShadow()
  for i in range(81):
    shadow.update(sample(i*.05), evidence())
  row = sample(4.05)
  row.update(changes)
  assert shadow.update(row, evidence())['delta_accel'] == 0


@pytest.mark.parametrize('gain', [0, 1.1, math.nan])
def test_invalid_gain(gain):
  with pytest.raises(ValueError):
    UncertaintyShadow(gain=gain)
