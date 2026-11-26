from dataclasses import replace
import math

import pytest

from openpilot.tools.curve_centering.simulation import Scenario, compare_pair, grid, road_curvature, run


def test_straight_equilibrium():
  for arm in ('A', 'C', 'U'):
    result = run(Scenario(peak_curvature=0, model_bias=0), arm)
    assert result['valid']
    assert result['rms_m'] == 0


def test_mirrored_closed_loop():
  original = Scenario(peak_curvature=.01, model_bias=.3, differential_error=.2)
  mirrored = replace(original, direction=-1, model_bias=-.3, differential_error=-.2)
  for arm in ('A', 'C', 'U'):
    left, right = run(original, arm), run(mirrored, arm)
    assert left['valid'] == right['valid']
    assert left['rms_m'] == pytest.approx(right['rms_m'], abs=1e-10)
    assert left['peak_m'] == pytest.approx(right['peak_m'], abs=1e-10)


def test_differential_error_negative_case_and_uncertainty_abstention():
  case = Scenario(peak_curvature=0, model_bias=0, differential_error=.2)
  baseline, legacy, bounded = (run(case, arm) for arm in ('A', 'C', 'U'))
  assert legacy['rms_m'] > .05  # Preserve the harmful legacy counterexample.
  assert baseline['rms_m'] == 0
  assert bounded['rms_m'] < 1e-12


def test_independent_feedback_improves_known_straight_bias():
  case = Scenario(peak_curvature=0, model_bias=.3)
  a, u = run(case, 'A', retain_trace=True), run(case, 'U', retain_trace=True)
  assert u['rms_m'] < a['rms_m']
  assert a['trace'][-1]['y'] != u['trace'][-1]['y']


@pytest.mark.parametrize('arm', ['A', 'C', 'U'])
def test_original_rate_limit_is_applied(arm):
  case = Scenario()
  assert run(case, arm)['max_command_rate'] <= 5/case.speed**2 + 1e-12


@pytest.mark.parametrize('fault', ['line_loss', 'stale', 'takeover'])
def test_faults_are_exercised(fault):
  result = run(Scenario(peak_curvature=0, fault=fault), 'U')
  assert result['valid']
  assert result['reasons'][fault] > 0


@pytest.mark.parametrize('changes', [{'speed':0}, {'delay':-1}, {'lag':0}, {'differential_error':math.nan}, {'fault':'unsupported'}])
def test_invalid_scenario(changes):
  with pytest.raises(ValueError):
    replace(Scenario(), **changes)


def test_profile_and_grid():
  case = Scenario()
  assert road_curvature(0, case) == road_curvature(23, case) == 0
  cases = list(grid())
  assert len(cases) == 320
  assert any(abs(c.differential_error) > c.assumed_error_bound for c in cases)


def test_invalid_runs_are_not_passes():
  a = {'valid':False, 'rms_m':0, 'peak_m':0}
  comparison = compare_pair(a, a)
  assert comparison['valid_pair'] is False
  assert comparison['regression'] is None


def test_regression_threshold_and_peak_rms_tradeoff():
  a = {'valid':True, 'rms_m':.3, 'peak_m':.4}
  b = {'valid':True, 'rms_m':.2, 'peak_m':.5}
  comparison = compare_pair(a, b)
  assert comparison['regression'] and comparison['rms_improved']

def test_numerically_valid_does_not_mean_within_lane():
  result = run(Scenario(speed=18, peak_curvature=.01, delay=.3), 'A')
  assert result['boundary_exceeded_steps'] > 0
  assert not result['within_assumed_lane']
