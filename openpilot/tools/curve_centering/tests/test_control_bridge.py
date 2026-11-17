import copy
from dataclasses import replace
import math
from pathlib import Path
import random

import pytest

from openpilot.tools.curve_centering.control_bridge import ControlBridge, ControlTick
from openpilot.tools.curve_centering.model_baseline import model_step
from openpilot.tools.curve_centering.source_control import PINNED_BLOBS, ROOT, SourceControl, load_source
from openpilot.tools.curve_centering.observer import Observer


def inputs(i, **changes):
  ns = i*10_000_000
  model_ns = (i//5)*50_000_000
  tick = ControlTick(ns, model_ns, ns, ns, .001, 12., .001, 0., True,
                     False, False, False, False, False, False, True, False, 0., 0., False)
  row = {'t': model_ns/1e9, 'model_t': model_ns/1e9, 'model_action_curvature': .001,
         'speed_kph': 43.2, 'eligible': True, 'lat_active': True, 'driver_pressed': False,
         'lane_change_state': 'off', 'desire': 'none', 'reasons': [],
         'steering_saturated': False, 'lateral_accel_error_mps2': 0., 'use_lane_lines': False,
         'geometry': {'samples': [{'x_m': 20., 'raw_error_m': .5}]}}
  return replace(tick, **changes), {'model_ns': model_ns, 'available_ns': model_ns, 'row': row}


def warm(mode='isolated'):
  bridge = ControlBridge(mode)
  for i in range(301):
    result = bridge.step(*inputs(i))
  assert result['injected_delta_curvature'] != 0
  return bridge, result


def test_actual_production_statements_match_scalar_reference():
  source = SourceControl()
  rng = random.Random(52)
  for _ in range(2000):
    args = {'speed': rng.uniform(0, 45), 'previous': rng.uniform(-.02, .02), 'action': rng.uniform(-.02, .02),
                'feedback': rng.uniform(-.02, .02), 'roll': rng.uniform(-.1, .1),
                'active': rng.choice([True, False]), 'lateral_started': rng.choice([True, False])}
    expected = model_step(**args)
    actual = source.step(**args)
    assert actual['curvature'] == pytest.approx(expected.curvature, abs=1e-15)
    assert actual['curvature_limited'] == expected.curvature_limited


def test_source_drift_rejected(tmp_path):
  for name in PINNED_BLOBS:
    target = tmp_path/name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((ROOT/name).read_bytes()+b'\n')
  with pytest.raises(ValueError, match='unreviewed production source'):
    load_source(tmp_path)


def test_shadow_default_never_selects_candidate():
  bridge, result = warm('shadow')
  assert ControlBridge().mode == 'shadow'
  assert result['selected_curvature'] == result['baseline']['curvature']
  assert result['selected_curvature'] != result['candidate']['curvature']
  assert not result['vehicle_output'] and not result['deployment_approved']
  with pytest.raises(ValueError):
    ControlBridge('vehicle')
  assert bridge.mode == 'shadow'


@pytest.mark.parametrize('flag', ['driver_steering', 'driver_gas', 'driver_brake', 'maneuver', 'saturated', 'safety_limited'])
def test_tick_guards_between_model_frames_and_residual_is_visible(flag):
  bridge, before = warm()
  tick, obs = inputs(301, **{flag: True})
  result = bridge.step(tick, obs)
  assert result['injected_delta_curvature'] == 0
  # Withdrawal stops injection; it does NOT erase prior smoothing state.
  assert result['residual_curvature'] != 0
  assert abs(result['residual_curvature']) < abs(before['residual_curvature'])
  for i in range(302, 399):
    assert bridge.step(*inputs(i))['injected_delta_curvature'] == 0


@pytest.mark.parametrize('change', [{'lat_active': False}, {'speed': 4.}])
def test_inactive_low_speed_withdraw(change):
  bridge, _ = warm()
  assert bridge.step(*inputs(301, **change))['injected_delta_curvature'] == 0


@pytest.mark.parametrize('field,value', [('now_ns', -1), ('action', math.nan), ('speed', -1),
                                        ('driver_brake', None), ('saturated', 0), ('messages_valid', False),
                                        ('model_ns', 0), ('car_state_ns', 0), ('parameters_ns', 0),
                                        ('model_ns', 4_000_000_000), ('now_ns', 3_000_000_000), ('now_ns', 4_000_000_000)])
def test_invalid_or_stale_control_stops_trial_without_fake_command(field, value):
  bridge, _ = warm()
  result = bridge.step(*inputs(301, **{field: value}))
  assert result['selected_curvature'] is None
  assert result['injected_delta_curvature'] == 0


def test_actual_lane_source_selection_and_vw():
  # Planner flag alone is not selected control mode; threshold is essential.
  bridge = ControlBridge()
  tick, obs = inputs(0, use_lane_lines=True, curve_speed=10., lane_threshold=20.)
  obs['row']['use_lane_lines'] = True
  assert bridge.step(tick, obs)['baseline'] is not None
  for kwargs in ({'use_lane_lines': True, 'curve_speed': 21., 'lane_threshold': 20.}, {'vw_meb': True}):
    bridge, _ = warm()
    result = bridge.step(*inputs(301, **kwargs))
    assert result['selected_curvature'] is None
    assert result['reasons'] == ['unsupported_lane_or_vw_mode']


@pytest.mark.parametrize('fault', ['missing', 'id', 'future', 'action', 'geometry', 'tracking', 'eligible', 'duplicate_mutation'])
def test_observer_faults_block_and_require_full_reentry(fault):
  bridge, _ = warm()
  tick, obs = inputs(301)
  if fault == 'missing':
    obs = None
  elif fault == 'id':
    obs['model_ns'] -= 1
  elif fault == 'future':
    obs['available_ns'] = tick.now_ns+1
  elif fault == 'action':
    obs['row']['model_action_curvature'] += .001
  elif fault == 'geometry':
    obs['row']['geometry'] = None
  elif fault == 'tracking':
    obs['row']['lateral_accel_error_mps2'] = .21
  elif fault == 'eligible':
    obs['row']['eligible'] = False
  else:
    obs['row']['geometry']['samples'][0]['raw_error_m'] += .01
  result = bridge.step(tick, obs)
  assert result['injected_delta_curvature'] == 0
  assert result['reasons']
  for i in range(302, 399):
    assert bridge.step(*inputs(i))['injected_delta_curvature'] == 0
  for i in range(399, 501):
    result = bridge.step(*inputs(i))
  assert result['injected_delta_curvature'] != 0


def test_delta_acceleration_bound_uses_current_speed():
  bridge, _ = warm()
  result = bridge.step(*inputs(301, speed=6.))
  assert abs(result['injected_delta_curvature']*6**2) <= .25


def test_real_observer_output_to_production_source_path():
  from openpilot.tools.curve_centering.bridge_demo import synthetic_records
  observer, bridge = Observer(), ControlBridge('isolated')
  observation = None
  for i in range(601):
    tick, _ = inputs(i)
    if i % 5 == 0:
      for record in synthetic_records(tick.model_ns):
        row = observer.feed(record)
        if row is not None:
          observation = {'row': row, 'model_ns': tick.model_ns, 'available_ns': tick.model_ns}
    result = bridge.step(tick, observation)
  assert result['injected_delta_curvature'] < 0
  assert result['selected_curvature'] == result['candidate']['curvature']
  assert result['selected_curvature'] != result['baseline']['curvature']
  assert not result['vehicle_output']


def test_demo_all_faults_have_blocking_evidence_and_shadow_parity():
  from openpilot.tools.curve_centering.bridge_demo import FAULTS, demo_ticks
  bridge = ControlBridge()
  blocked = set()
  active = 0
  for tick, observation, fault in demo_ticks():
    r = bridge.step(tick, observation)
    assert r['selected_curvature'] == (r['baseline']['curvature'] if r['baseline'] else None)
    if r['injected_delta_curvature'] == 0 and r['reasons']:
      blocked.add(fault)
    active += r['injected_delta_curvature'] != 0
  assert set(FAULTS.values()) <= blocked
  assert active > 0


def test_input_observation_not_mutated():
  bridge = ControlBridge()
  tick, obs = inputs(0)
  before = copy.deepcopy(obs)
  bridge.step(tick, obs)
  assert obs == before


def test_no_production_import_of_bridge():
  for folder in ('selfdrive', 'system', 'common'):
    for path in (ROOT/folder).rglob('*.py'):
      if path != ROOT/'selfdrive/controls/controlsd.py':
        assert 'tools.curve_centering' not in path.read_text(errors='replace'), str(path)
  assert not (Path(__file__).parents[1]/'control_bridge.py').read_text().count('PubMaster')


@pytest.mark.parametrize('geometry', [[], 3, {'samples': None}, {'samples': [None]}, {'samples': [{'x_m': 20., 'raw_error_m': math.nan}]}])
def test_malformed_geometry_withdraws(geometry):
  bridge, _ = warm()
  tick, obs = inputs(301)
  obs['row']['geometry'] = geometry
  result = bridge.step(tick, obs)
  assert result['injected_delta_curvature'] == 0
  assert 'invalid_geometry' in result['reasons']


def test_withdrawal_has_zero_same_state_policy_difference():
  bridge, _ = warm()
  tick, obs = inputs(301, driver_steering=True)
  result = bridge.step(tick, obs)
  assert result['policy_delta_curvature'] == 0
  assert result['residual_curvature'] != 0  # different historical states, not new injection


def test_available_time_can_follow_plan_publication_without_lookahead():
  tick, obs = inputs(1)
  obs['available_ns'] = tick.now_ns
  result = ControlBridge().step(tick, obs)
  assert 'unmatched_stale_or_future_observation' not in result['reasons']
