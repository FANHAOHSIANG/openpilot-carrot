import time

import pytest

from openpilot.cereal import log

from openpilot.selfdrive.controls.tests.test_controlsd_publish import publish_fixture
from openpilot.selfdrive.controls.tests.test_curve_centering import curve_model
from openpilot.selfdrive.controls.tests.test_lateral_startup_control import control_fixture


@pytest.fixture
def drive(monkeypatch):
  control, step = control_fixture(fingerprint='HYUNDAI_IONIQ_5')
  sm = control.sm
  control.lateral_started = control.lateral_startup.ready = True
  control.curve_centering_enabled = True
  sm['carState'].vEgo = sm['carState'].vEgoRaw = 15.0
  sm['carrotMan'].activeCarrot = sm['carrotMan'].xDistToTurn = 0
  sm.recv_time = {}
  sm['carrotMan'].desiredSpeed = 80.0
  sm.seen['carrotMan'] = sm.alive['carrotMan'] = sm.valid['carrotMan'] = True
  sm['liveCalibration'] = log.LiveCalibrationData.new_message(calStatus='calibrated')
  sm.valid['liveCalibration'] = sm.alive['liveCalibration'] = sm.freq_ok['liveCalibration'] = True
  sm.logMonoTime = {}
  sm.updated = {}
  model = sm['modelV2']
  source = curve_model()
  model.action.desiredCurvature = source.action.desiredCurvature
  model.position.x, model.position.y = source.position.x, source.position.y
  model.laneLines = [dict(x=line.x, y=line.y) for line in source.laneLines]
  model.laneLineProbs, model.laneLineStds = source.laneLineProbs, source.laneLineStds

  now = 10_000_000_000
  monkeypatch.setattr(time, 'monotonic_ns', lambda: now)
  monkeypatch.setattr(time, 'monotonic', lambda: now * 1e-9)

  def tick(*, camera=True, duplicate=False, elapsed_ms=None, car_age_ms=0):
    nonlocal now
    now += (elapsed_ms if elapsed_ms is not None else (50 if camera else 10)) * 1_000_000
    sm.recv_time['carrotMan'] = (now - 2_000_000) / 1e9
    sm.logMonoTime['carState'] = now - car_age_ms * 1_000_000
    sm.recv_time['carState'] = sm.logMonoTime['carState'] / 1e9
    sm.updated['modelV2'] = camera
    if camera:
      if not duplicate:
        model.frameId += 1
        model.timestampEof = now - 10_000_000
      sm.logMonoTime['modelV2'] = now
      sm.recv_time['modelV2'] = (now - 1_000_000) / 1e9
    return step()[0]

  return control, tick


def test_one_camera_frame_counts_once_and_correction_reaches_actuator_target(drive):
  control, tick = drive
  target = control.sm['modelV2'].action.desiredCurvature
  for _ in range(3):
    tick()
    for _ in range(4):
      tick(camera=False)
      assert control.curve_centering_delta == 0
  control.desired_curvature = target
  cc = tick()
  delta = control.curve_centering_delta
  assert cc.latActive and delta < 0
  assert target + delta < cc.actuators.curvature < target  # production smoothing still applies
  tick(camera=False)
  assert control.curve_centering_delta == delta
  tick(duplicate=True)
  assert control.curve_centering_delta == 0
  for _ in range(3):
    tick()
    assert control.curve_centering_delta == 0
  tick()
  assert control.curve_centering_delta < 0


@pytest.mark.parametrize('veto', ['toggle', 'lane_mode', 'driver', 'blinker', 'lane_change', 'navigation',
                                   'stale_camera', 'stale_receipt', 'stale_car', 'invalid_car', 'invalid_model',
                                   'low_speed', 'uncalibrated', 'invalid_calibration'])
def test_veto_on_intermediate_control_tick_drops_held_correction(drive, veto):
  control, tick = drive
  for _ in range(5):
    tick()
  assert control.curve_centering_delta < 0
  sm = control.sm
  if veto == 'toggle':
    control.curve_centering_enabled = False
  elif veto == 'lane_mode':
    sm['lateralPlan'].useLaneLines = True
  elif veto == 'driver':
    sm['carState'].steeringPressed = True
  elif veto == 'blinker':
    sm['carState'].rightBlinker = True
  elif veto == 'lane_change':
    sm['modelV2'].meta.laneChangeState = 'preLaneChange'
  elif veto == 'navigation':
    sm['carrotMan'].activeCarrot, sm['carrotMan'].xDistToTurn = 2, 50
  elif veto == 'stale_receipt':
    sm.recv_time['modelV2'] -= 1.0
  elif veto == 'low_speed':
    sm['carState'].vEgo = 8.0
  elif veto == 'uncalibrated':
    sm['liveCalibration'].calStatus = 'uncalibrated'
  elif veto == 'invalid_calibration':
    sm.valid['liveCalibration'] = False
  elif veto == 'invalid_car':
    sm.valid['carState'] = False
  elif veto == 'invalid_model':
    sm.valid['modelV2'] = False
  tick(camera=False, elapsed_ms=210 if veto == 'stale_camera' else 10, car_age_ms=150 if veto == 'stale_car' else 0)
  assert control.curve_centering_delta == 0


@pytest.mark.parametrize('enabled', [False, True])
def test_opt_in_preserves_longitudinal_output(drive, enabled):
  control, tick = drive
  target = control.sm['modelV2'].action.desiredCurvature
  control.desired_curvature = target
  control.curve_centering_enabled = enabled
  control.LoC.update = lambda *args: (0.42, 0.42, 0.2)
  for _ in range(6):
    cc = tick()
  assert cc.latActive
  assert (control.curve_centering_delta < 0.0) == enabled
  assert cc.actuators.accel == pytest.approx(0.42)
  if not enabled:
    assert cc.actuators.curvature == pytest.approx(target)
  else:
    assert cc.actuators.curvature < target


@pytest.mark.parametrize('broken_frame', ['same_id', 'same_eof', 'late_after_gap'])
def test_a_discontinuity_requires_four_new_camera_observations(drive, broken_frame):
  control, tick = drive
  for _ in range(5):
    tick()
  assert control.curve_centering_delta < 0
  model = control.sm['modelV2']
  if broken_frame == 'late_after_gap':
    tick(elapsed_ms=240)
    recovery_count = 2  # this valid frame started the next run of four
  else:
    if broken_frame == 'same_id':
      model.timestampEof += 50_000_000
    else:
      model.frameId += 1
    tick(duplicate=True)
    recovery_count = 3
  assert control.curve_centering_delta == 0
  for _ in range(recovery_count):
    tick()
    assert control.curve_centering_delta == 0
  tick()
  assert control.curve_centering_delta < 0


@pytest.mark.parametrize('available', [False, True])
def test_parameter_poll_updates_live_only_on_supported_controls(available):
  control, _ = control_fixture(fingerprint='HYUNDAI_IONIQ_5' if available else '')
  feature_on = True
  control.params.get_bool = lambda key: key == 'ModelCurveCentering' and feature_on
  control.sm.update = lambda timeout: None
  control.sm.updated = dict(liveCalibration=False, livePose=False)
  control.sm.frame = 49
  control.update()
  assert not control.curve_centering_enabled
  control.sm.frame = 50
  control.update()
  assert control.curve_centering_enabled == available
  feature_on = False
  control.sm.frame = 100
  control.update()
  assert not control.curve_centering_enabled


def test_enabled_flag_and_signed_delta_are_published_in_controls_state():
  control, sent, publish = publish_fixture('hyundai', 0, True)
  control.curve_centering_enabled = True
  control.curve_centering_delta = -0.0002
  publish()
  state = sent['controlsState'].controlsState
  assert state.modelCurveCenteringEnabled
  assert state.modelCurveCenteringDelta == pytest.approx(control.curve_centering_delta)
