import math
import pytest
from openpilot.tools.curve_centering.centering_shadow import CenteringShadow, ShadowConfig


def sample(t, error=.5):
  return {'model_t':t, 'model_action_curvature':.002, 'speed_kph':72, 'eligible':True,
          'reasons':[], 'driver_pressed':False, 'lat_active':True, 'lane_change_state':'off',
          'desire':'none', 'lateral_accel_error_mps2':0, 'steering_saturated':False,
          'use_lane_lines':False, 'geometry':{'samples':[{'x_m':20.0, 'raw_error_m':error}]}}


def warm(error=.5):
  s = CenteringShadow()
  for i in range(81):
    r = s.update(sample(i*.05, error))
  return s, r


def test_mirror_and_bounds():
  _, left = warm(-.5)
  _, right = warm(.5)
  assert left['delta_accel'] == -right['delta_accel'] == .25
  assert right['geometric_shift_proxy_m'] < 0


def test_centered_no_correction():
  _, r = warm(0)
  assert r['delta_curvature'] == 0


@pytest.mark.parametrize('changes', [{'driver_pressed':True}, {'lat_active':False}, {'desire':'turnRight'},
                                    {'model_t':8}, {'model_action_curvature':math.nan}])
def test_immediate_withdrawal(changes):
  s, _ = warm()
  row = sample(4.05)
  row.update(changes)
  assert s.update(row)['delta_accel'] == 0


@pytest.mark.parametrize('changes', [{'eligible':False}, {'steering_saturated':True},
                                    {'lateral_accel_error_mps2':.4}, {'use_lane_lines':True}, {'geometry':None}])
def test_bad_quality_decays_without_increasing(changes):
  s, previous = warm()
  row = sample(4.05)
  row.update(changes)
  r = s.update(row)
  assert abs(r['delta_accel']) < abs(previous['delta_accel'])
  assert abs(r['delta_accel']-previous['delta_accel']) <= .25*.05+1e-12
  assert not r['active_candidate']


def test_requires_stable_recovery():
  s, _ = warm()
  row = sample(4.05)
  row['driver_pressed'] = True
  s.update(row)
  for i in range(19):
    assert s.update(sample(4.1+i*.05))['delta_accel'] == 0


def test_invalid_configuration():
  with pytest.raises(ValueError):
    ShadowConfig(max_delta_accel=-1)


@pytest.mark.parametrize('t', [4.0, 3.9, math.nan])
def test_duplicate_reverse_and_invalid_time_reset(t):
  s, _ = warm()
  assert s.update(sample(t))['delta_accel'] == 0


def test_geometry_loss_fully_exits_and_requires_recovery():
  s, _ = warm()
  for i in range(1, 25):
    row = sample(4+i*.05)
    row.update(eligible=False, geometry=None, reasons=['uncertain_lanes'])
    r = s.update(row)
  assert r['delta_accel'] == 0
  assert 'preview_geometry_unavailable' in r['reasons']
  for i in range(19):
    assert not s.update(sample(5.25+i*.05))['active_candidate']


def test_sign_reversal_slew_and_tracking_gate():
  s, prev = warm()
  r = s.update(sample(4.05, -.5))
  assert abs(r['delta_accel']-prev['delta_accel']) <= .0125+1e-12
  row = sample(4.1)
  row['lateral_accel_error_mps2'] = .21
  r = s.update(row)
  assert 'tracking_error_high' in r['reasons']
  assert not r['active_candidate']
