from copy import deepcopy

import pytest

from openpilot.tools.curve_centering.refined_shadow import RefinedShadow
from openpilot.tools.curve_centering.simulation import Scenario, compare_pair, run
from openpilot.tools.curve_centering.tests.test_centering_shadow import sample
from openpilot.tools.curve_centering.tests.test_uncertainty_shadow import evidence


@pytest.mark.parametrize('fault', ['bound_loss', 'expired', 'geometry', 'duplicate', 'tracking', 'saturated', 'mode', 'stale'])
def test_proposal_withdrawal_and_fresh_warmup(fault):
  candidate = RefinedShadow()
  for i in range(81):
    result = candidate.update(sample(i*.05), evidence())
  assert result['delta_accel'] != 0
  row, bound = sample(4.05), evidence()
  if fault == 'bound_loss':
    bound = None
  elif fault == 'expired':
    bound = evidence(valid_until=4.)
  elif fault == 'geometry':
    row['geometry'] = None
  elif fault == 'duplicate':
    row['geometry']['samples'] *= 2
  elif fault == 'tracking':
    row['lateral_accel_error_mps2'] = .21
  elif fault == 'saturated':
    row['steering_saturated'] = True
  elif fault == 'mode':
    row['use_lane_lines'] = True
  else:
    row['eligible'] = False
  before = deepcopy(row)
  result = candidate.update(row, bound)
  assert row == before
  assert result['delta_curvature'] == 0
  assert not result['active_candidate']
  for i in range(20):
    result = candidate.update(sample(4.1+i*.05), evidence())
    assert result['delta_curvature'] == 0
  assert candidate.update(sample(5.15), evidence())['active_candidate']


@pytest.mark.parametrize('error', [-.2, .2])
def test_false_correction_removed_without_changing_baseline(error):
  scenario = Scenario(model_bias=0., differential_error=error)
  baseline = run(scenario, 'A')
  original = run(scenario, 'C')
  refined = run(scenario, 'R')
  assert compare_pair(baseline, original)['regression']
  for metric in ('peak_m', 'rms_m', 'exit_peak_m', 'boundary_exceeded_steps'):
    assert refined[metric] == pytest.approx(baseline[metric], abs=1e-12)


def test_retained_stale_case_is_not_falsely_declared_safe():
  scenario = Scenario(delay=.3, fault='stale')
  a, c, r = [run(scenario, arm) for arm in ('A', 'C', 'R')]
  assert compare_pair(a, c)['regression']
  assert not compare_pair(a, r)['regression']
  assert not r['within_assumed_lane']
  assert r['peak_m'] > scenario.half_clearance_m
