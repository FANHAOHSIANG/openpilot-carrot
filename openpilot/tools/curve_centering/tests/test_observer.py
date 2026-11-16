import copy
import json
import math
from pathlib import Path
import tempfile
import pytest
from openpilot.tools.curve_centering.observer import Config, Observer, geometry
from openpilot.tools.curve_centering.replay import episodes, replay, summarize
from openpilot.tools.curve_centering.report import render_report


def sample(t=10.0, curvature=0.001, raw_bias=0.0, request_bias=0.0, center_offset=0.0, direction='none', state='off'):
  xs = [float(x) for x in range(0, 42, 2)]
  ys = [center_offset + curvature * x * x / 2 for x in xs]

  def position(bias):
    return {'x': xs[:], 'y': [y + bias for y in ys]}

  model = {
    'laneLines': [position(-5.4), position(-1.8), position(1.8), position(5.4)],
    'laneLineProbs': [0.9] * 4,
    'laneLineStds': [0.1] * 4,
    'position': position(raw_bias),
    'meta': {'laneChangeState': state, 'desire': direction},
  }
  plan = {
    'modelMonoTime': round(t * 1000000000.0),
    'mpcSolutionValid': True,
    'useLaneLines': True,
    'dPathPoints': [y + request_bias for y in ys],
    'position': position(request_bias / 2),
  }
  data = {
    'carState': {'vEgo': 20.0, 'steeringPressed': False, 'leftBlinker': False, 'rightBlinker': False},
    'carControl': {'latActive': True},
    'controlsState': {'lateralControlState': {'torqueState': {'active': True, 'saturated': False, 'actualLateralAccel': 0.4, 'desiredLateralAccel': 0.4}}},
    'modelV2': model,
    'lateralPlan': plan,
  }
  return [
    {
      'kind': k,
      't': t + (0.01 if k == 'lateralPlan' else 0),
      'mono_ns': round((t + (0.01 if k == 'lateralPlan' else 0)) * 1000000000.0),
      'valid': True,
      'data': v,
    }
    for k, v in data.items()
  ]


def feed(observer, records):
  result = None
  for r in records:
    value = observer.feed(r)
    if value is not None:
      result = value
  return result


def settled(**kwargs):
  o = Observer()
  result = None
  for i in range(30):
    result = feed(o, sample(10 + i * 0.05, **kwargs))
  return (o, result)


class TestGeometry:
  def test_centered_both_directions(self):
    for curvature in (-0.002, 0.002):
      _, r = settled(curvature=curvature)
      assert r['eligible']
      assert r['geometry']['request_bias_m'] == pytest.approx(0, abs=1e-07)
      assert r['direction'] == ('left' if curvature < 0 else 'right')

  def test_mirror_inward_bias(self):
    for sign in (-1, 1):
      _, r = settled(curvature=sign * 0.002, request_bias=sign * 0.35)
      assert r['geometry']['inward_request_bias_m'] > 0.3
      assert 'requested_path_bias' in r['findings']

  def test_raw_path_vs_requested_path(self):
    _, r = settled(raw_bias=0.5, request_bias=0)
    assert 'raw_model_path_bias' in r['findings']
    assert 'requested_path_bias' not in r['findings']
    _, r = settled(raw_bias=0, request_bias=-0.4)
    assert 'raw_model_path_bias' not in r['findings']
    assert 'requested_path_bias' in r['findings']

  def test_offset_not_claimed_as_body_measurement(self):
    _, r = settled(center_offset=0.3)
    assert r['geometry']['origin_offset_m'] == pytest.approx(-0.3, abs=0.001)
    assert r['geometry']['vehicle_offset_m'] is None
    assert r['geometry']['estimated_body_clearance_m'] is None

  def test_explicit_body_calibration(self):
    records = sample(curvature=0, center_offset=0.3)
    g = geometry(records[-2]['data'], records[-1]['data'], Config(vehicle_center_y_m=0.1, vehicle_width_m=1.9))
    assert g['vehicle_offset_m'] == pytest.approx(-0.2, abs=1e-07)
    assert g['estimated_body_clearance_m'] == pytest.approx(0.65, abs=1e-07)

  def test_unequal_lane_x_grids(self):
    records = sample(curvature=0)
    m, p = (records[-2]['data'], records[-1]['data'])
    m['laneLines'][2] = {'x': [0.0, 1.0, 3.0, 7.0, 20.0, 40.0], 'y': [1.8] * 6}
    assert geometry(m, p, Config())['request_bias_m'] == pytest.approx(0, abs=1e-07)

  def test_no_extrapolation(self):
    records = sample()
    records[-1]['data']['position'] = {'x': [0.0, 2.0, 4.0], 'y': [0.0, 0.0, 0.0]}
    r = feed(Observer(), records)
    assert 'insufficient_horizon' in r['reasons']
    assert r['geometry'] is None

  def test_partial_horizon_keeps_exact_endpoint(self):
    for horizon in (10.5, 19.5, 23.0, 29.5):
      records = sample(curvature=0)
      records[-1]['data']['position'] = {'x': [0.0, 5.0, horizon], 'y': [0.0, 0.0, 0.0]}
      g = geometry(records[-2]['data'], records[-1]['data'], Config())
      assert g['horizon_m'] == horizon
      assert g['plot']['x'][-1] == horizon
      assert all(s['x_m'] <= horizon for s in g['samples'])
      assert g['request_bias_m'] == pytest.approx(0, abs=1e-7)

  def test_bad_geometry(self):
    for mutation in ('nan', 'duplicate', 'reverse', 'crossing', 'lowprob', 'std', 'missing'):
      records = sample()
      m = records[-2]['data']
      if mutation == 'nan':
        m['laneLines'][1]['y'][3] = math.nan
      if mutation == 'duplicate':
        m['laneLines'][1]['x'][3] = m['laneLines'][1]['x'][2]
      if mutation == 'reverse':
        m['laneLines'][1]['x'].reverse()
      if mutation == 'crossing':
        m['laneLines'][1], m['laneLines'][2] = (m['laneLines'][2], m['laneLines'][1])
      if mutation == 'lowprob':
        m['laneLineProbs'][1] = 0.2
      if mutation == 'std':
        m['laneLineStds'][2] = 0.8
      if mutation == 'missing':
        m['laneLines'] = []
      r = feed(Observer(), records)
      assert not r['eligible'], mutation
      assert r['geometry'] is None, mutation

  def test_inputs_not_mutated(self):
    records = sample()
    original = copy.deepcopy(records)
    feed(Observer(), records)
    assert records == original


class TestAdmission:
  def test_model_action_and_actual_command_are_distinct_from_mpc_geometry(self):
    records = sample(request_bias=0.6)
    records[-2]['data']['action'] = {'desiredCurvature': 0.001}
    records[1]['data']['actuators'] = {'curvature': 0.002}
    records[2]['data']['curvature'] = 0.003
    r = feed(Observer(), records)
    assert r['model_action_curvature'] == 0.001
    assert r['command_curvature'] == 0.002
    assert r['estimated_curvature'] == 0.003
    assert r['geometry']['request_bias_m'] > 0.5

  def test_exact_model_join_not_nearest(self):
    records = sample()
    records[-1]['data']['modelMonoTime'] += 1
    r = feed(Observer(), records)
    assert r['reasons'] == ['unmatched_model']

  def test_stale_or_future_model(self):
    for delta in (-0.01, 0.4):
      records = sample()
      records[-1]['t'] = records[-2]['t'] + delta
      assert 'stale_or_future_model' in feed(Observer(), records)['reasons']

  def test_state_future_or_stale(self):
    for delta in (-0.3, 0.01):
      records = sample()
      records[0]['t'] += delta
      assert 'stale_carState' in feed(Observer(), records)['reasons']

  def test_invalid_messages(self):
    for i in range(5):
      records = sample()
      records[i]['valid'] = False
      r = feed(Observer(), records)
      assert not r['eligible']
      assert r['geometry'] is None

  def test_driver_override_and_control_off(self):
    for key in ('steeringPressed', 'brakePressed', 'gasPressed'):
      o, _ = settled()
      records = sample(11.5)
      records[0]['data'][key] = True
      assert 'driver_override' in feed(o, records)['reasons']
    o, _ = settled()
    records = sample(11.5)
    records[1]['data']['latActive'] = False
    assert 'lateral_inactive' in feed(o, records)['reasons']

  def test_lane_change_and_recovery(self):
    o, _ = settled()
    r = feed(o, sample(11.5, direction='laneChangeLeft', state='laneChangeFinishing'))
    assert 'maneuver' in r['reasons']
    for i in range(1, 39):
      r = feed(o, sample(11.5 + i * 0.05))
      assert 'maneuver_recovery' in r['reasons']
      assert not r['eligible']
    for i in range(39, 65):
      r = feed(o, sample(11.5 + i * 0.05))
    assert r['eligible']

  def test_geometry_jump_and_message_gap_reset_warmup(self):
    o, _ = settled()
    r = feed(o, sample(11.5, center_offset=0.6))
    assert 'lane_geometry_jump' in r['reasons']
    o, _ = settled()
    r = feed(o, sample(15))
    assert 'warming_up' in r['reasons']

  def test_no_tuning_on_insufficient_evidence(self):
    r = feed(Observer(), sample(raw_bias=0.8, request_bias=0.7))
    assert r['findings'] == []
    assert not r['eligible']

  def test_no_repeat_plan(self):
    o, _ = settled()
    assert feed(o, sample(11.45))['reasons'] == ['nonmonotonic_plan']

  def test_config_validation(self):
    for config in ({'min_lane_probability': 2}, {'vehicle_width_m': -1}, {'vehicle_center_y_m': math.nan}):
      with pytest.raises(ValueError):
        Config(**config)


class TestReport:
  def test_episode_boundaries(self):
    o, _ = settled()
    rows = []
    for i in range(30):
      r = feed(o, sample(11.5 + i * 0.05, request_bias=0.4 if i < 15 else -0.4))
      r.update(source='fixture', relative_s=i * 0.05)
      rows.append(r)
    assert len(episodes(rows)) == 2
    rows[3]['eligible'] = False
    assert len(episodes(rows)) == 2
    assert summarize(rows)['eligible_frames'] == 29

  def test_report_escapes_script_and_filename(self):
    payload = '</script><script>alert(1)</script>'
    html = render_report({'rows': [], 'sources': [{'name': payload}]})
    assert payload not in html
    assert '__REPORT_DATA__' not in html
    assert '__LIVE_MODE__' not in html

  def test_corrupt_file_is_visible(self):
    with tempfile.TemporaryDirectory() as tmp:
      path = Path(tmp) / 'bad.rlog'
      path.write_bytes(b'broken')
      report = replay([path, path])
      assert report['sources'][0]['status'] == 'error'
      assert report['sources'][1]['status'] == 'duplicate_skipped'
      assert report['rows'] == []

  def test_full_cereal_schema_replay(self):
    from openpilot.cereal import log

    with tempfile.TemporaryDirectory() as tmp:
      path = Path(tmp) / 'synthetic.rlog'
      events = []
      for i in range(30):
        for record in sample(10 + 0.05 * i, request_bias=0.3):
          event = log.Event.new_message(logMonoTime=record['mono_ns'], valid=True)
          event.init(record['kind'])
          getattr(event, record['kind']).from_dict(record['data'])
          events.append(event.to_bytes())
      path.write_bytes(b''.join(events))
      report = replay([path])
      assert report['sources'][0]['status'] == 'ok', report['sources']
      assert report['summary']['frames'] == 30
      assert report['summary']['eligible_frames'] > 5
      json.dumps(report, allow_nan=False)
