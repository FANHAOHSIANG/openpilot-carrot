from copy import deepcopy

import numpy as np
import pytest

from openpilot.tools.clearance_shadow.policy import Config, OffsetObserver


def line(y):
  return {'x': [0, 10, 20, 30, 50], 'y': [y] * 5}


def scene(t=0):
  return {'t': t, 'valid': True, 'model_age_s': 0.05, 'speed_mps': 20, 'curvature': 0.0,
          'lat_active': True, 'steering_pressed': False, 'blinker': False, 'maneuver': False,
          'lane_lines': [line(-5.4), line(-1.8), line(1.8), line(5.4)], 'lane_probs': [0.9, 0.95, 0.95, 0.1],
          'road_edges': [line(-6), line(2.2)], 'edge_stds': [0.1, 0.1], 'path': line(0), 'perception_valid': True}


def truck(side='right', track=1, label='truck'):
  lo, hi = (2.1, 4.5) if side == 'right' else (-4.5, -2.1)
  return {'label': label, 'confidence': 0.9, 'track_id': track, 'x_m': 12,
          'y_min_m': lo, 'y_max_m': hi, 'geometry_valid': True}


def run(observer, objects=(), modify=None, frames=100):
  results = []
  for i in range(frames):
    s = scene(i * 0.05)
    if modify:
      modify(s)
    results.append(observer.update(s, objects))
  return results


@pytest.mark.parametrize('side,sign', [('right', -1), ('left', 1)])
@pytest.mark.parametrize('label', ['truck', 'bus'])
def test_actual_large_vehicle_direction_and_slew(side, sign, label):
  out = run(OffsetObserver(), [truck(side, label=label)])
  assert out[-1]['candidate_offset_m'] == pytest.approx(sign * 0.15)
  values = np.array([r['candidate_offset_m'] for r in out])
  assert np.max(np.abs(np.diff(values))) <= 0.0025 + 1e-10
  assert all(r['applied_offset_m'] == 0 and r['control_eligible'] is False for r in out)


def test_hcop_port_needs_positive_evidence_not_two_missing_outer_lines():
  assert run(OffsetObserver(mode='roadside'))[-1]['candidate_offset_m'] == pytest.approx(-0.15)
  out = run(OffsetObserver(mode='roadside'), modify=lambda s: s.update(lane_probs=[0.1, 0.95, 0.95, 0.1]))
  assert all(r['candidate_offset_m'] == 0 for r in out)


@pytest.mark.parametrize('key,value', [('lat_active', False), ('steering_pressed', True), ('blinker', True),
                                    ('maneuver', True), ('valid', False), ('model_age_s', 0.5),
                                    ('model_age_s', -0.01), ('speed_mps', 2), ('curvature', 0.01),
                                    ('curvature', float('nan')), ('perception_valid', False)])
def test_gates(key, value):
  out = run(OffsetObserver(), [truck()], modify=lambda s: s.update({key: value}))
  assert all(r['candidate_offset_m'] == 0 for r in out)


@pytest.mark.parametrize('other', ['truck', 'bus', 'car', 'motorcycle', 'bicycle', 'person', 'train'])
def test_opposite_side_actors_block(other):
  out = run(OffsetObserver(), [truck(), truck('left', track=2, label=other)])
  assert out[-1]['reason'] == 'actors on both sides'
  assert out[-1]['candidate_offset_m'] == 0


@pytest.mark.parametrize('change', [{'track_id': None}, {'confidence': 0.4}, {'label': 'car'},
                                  {'geometry_valid': False}, {'y_min_m': 1.6}, {'x_m': 80}])
def test_unqualified_or_intruding_object(change):
  out = run(OffsetObserver(), [dict(truck(), **change)])
  assert out[-1]['candidate_offset_m'] == 0


def test_identity_switch_cannot_accumulate_confirmation():
  obs = OffsetObserver()
  for i in range(80):
    result = obs.update(scene(i * 0.05), [truck(track=i)])
    assert result['candidate_offset_m'] == 0


def test_repeated_frame_cannot_confirm():
  obs = OffsetObserver()
  for _ in range(100):
    assert obs.update(scene(1), [truck()])['candidate_offset_m'] == 0


def test_gap_and_invalid_geometry_clear_previous_candidate():
  obs = OffsetObserver()
  assert run(obs, [truck()])[-1]['candidate_offset_m'] < -0.1
  assert obs.update(scene(20), [truck()])['candidate_offset_m'] == 0
  s = scene(20.05)
  s['lane_lines'][1] = {'x': [0, 1], 'y': [-1.8, -1.8]}
  assert obs.update(s, [truck()])['candidate_offset_m'] == 0


def test_opposite_target_passes_through_center():
  obs = OffsetObserver()
  run(obs, [truck()])
  values = [obs.update(scene(5 + i * 0.05), [truck('left')])['candidate_offset_m'] for i in range(150)]
  assert 0.0 in values
  assert values[-1] > 0.1


def test_cleared_detection_returns_to_zero():
  obs = OffsetObserver()
  run(obs, [truck()])
  values = [obs.update(scene(5 + i * 0.05), [])['candidate_offset_m'] for i in range(80)]
  assert values[-1] == 0
  assert np.max(np.abs(np.diff(values))) <= 0.0025 + 1e-10


def test_corridor_limits_consider_existing_path_offset_and_preview():
  def shifted(s):
    s['path'] = line(-0.40)  # only 5 cm further room on left after vehicle envelope and margin
  out = run(OffsetObserver(), [truck()], modify=shifted)
  assert out[-1]['candidate_offset_m'] == pytest.approx(-0.05)
  def narrow_ahead(s):
    s['lane_lines'][2]['y'][2] = 0.4
  assert run(OffsetObserver(), [truck()], modify=narrow_ahead)[-1]['candidate_offset_m'] == 0


@pytest.mark.parametrize('prob', [0.2, float('nan'), -1, 1.5])
def test_invalid_lane_confidence(prob):
  out = run(OffsetObserver(), [truck()], modify=lambda s: s['lane_probs'].__setitem__(1, prob))
  assert out[-1]['candidate_offset_m'] == 0


def test_road_edge_not_just_missing_outer_line():
  assert run(OffsetObserver(mode='roadside'), modify=lambda s: s.update(edge_stds=[0.1, 1]))[-1]['candidate_offset_m'] == 0
  assert run(OffsetObserver(mode='roadside'), modify=lambda s: s['road_edges'].__setitem__(1, line(6)))[-1]['candidate_offset_m'] == 0


def test_config_is_bounded_and_zero_disables_candidate():
  for value in (-1, 1, float('nan')):
    with pytest.raises(ValueError):
      Config(max_offset_m=value)
  assert run(OffsetObserver(Config(max_offset_m=0)), [truck()])[-1]['candidate_offset_m'] == 0


def test_randomized_direction_and_corridor_invariants():
  rng = np.random.default_rng(7)
  for _ in range(100):
    shift = rng.uniform(-0.4, 0.4)
    side = str(rng.choice(['left', 'right']))
    obs = OffsetObserver()
    out = run(obs, [truck(side)], modify=lambda s, shift=shift: s.update(path=line(shift)))
    offset = out[-1]['candidate_offset_m']
    assert -0.15 <= offset <= 0.15
    assert -0.45 - 1e-9 <= shift + offset <= 0.45 + 1e-9
    assert (offset <= 0 if side == 'right' else offset >= 0)


def test_input_is_not_modified():
  s = scene()
  before = deepcopy(s)
  OffsetObserver().update(s, [truck()])
  assert s == before
