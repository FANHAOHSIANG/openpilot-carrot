import copy
from types import SimpleNamespace

import pytest

from opendbc.can import CANDefine, CANPacker
from opendbc.can.parser import CANParser, get_raw_value
from opendbc.car import structs
from opendbc.car.hyundai import hyundaicanfd
from opendbc.car.hyundai.hyundaicanfd import _select_cluster_background, _traffic_display_state
from opendbc.car.hyundai.values import CAR, HyundaiFlags


@pytest.fixture(autouse=True)
def fresh_cluster_state():
  # create_ccnc_messages caches its Params reads (re-read every 100 frames) and keeps display state on the function
  # object; clear both so every test sees its own keys and no state from another test
  names = ('_lane_line_check', '_cluster_display', '_traffic_background', '_lane_unseen', '_was_enabled', '_engage_popup',
           '_chime_shown', '_chime_until', '_gap_bars', '_gap_popup_until')

  def clear():
    for name in names:
      hyundaicanfd.create_ccnc_messages.__dict__.pop(name, None)
  clear()
  yield
  clear()


def cluster_params(display=0, traffic=0, hdp='0'):
  # Params stand-in: CcncClusterDisplay / CcncTrafficBackground (0 = that key's items off) and HDPuse
  keys = {'CcncClusterDisplay': display, 'CcncTrafficBackground': traffic}
  return lambda: SimpleNamespace(get_int=lambda key: keys.get(key, 0), get=lambda key: hdp if key == 'HDPuse' else '0')


@pytest.mark.parametrize(
  ("cruise_enabled", "lat_active", "paddle_pressed", "paddle_mode", "expected"),
  (
    (True, True, True, 0, 1),
    (False, True, True, 0, 3),
    (False, False, True, 0, 7),
    (True, True, True, 1, 6),
    (True, True, False, 1, 1),
  ),
)
def test_paddle_background_requires_enabled_paddle_mode(
  cruise_enabled, lat_active, paddle_pressed, paddle_mode, expected,
):
  assert _select_cluster_background(cruise_enabled, lat_active, paddle_pressed, paddle_mode) == expected


@pytest.mark.parametrize('cruise_enabled', (False, True))
@pytest.mark.parametrize('lat_active', (False, True))
def test_model_turn_background_requires_active_steering(cruise_enabled, lat_active):
  normal = 1 if cruise_enabled else 7
  assert _select_cluster_background(cruise_enabled, lat_active, False, 0, turning=True) == (6 if lat_active else normal)


@pytest.mark.parametrize('desire', range(5))
@pytest.mark.parametrize('lat_active', (False, True))
def test_turn_changes_only_background_in_existing_cluster_frame(monkeypatch, desire, lat_active):
  from openpilot.cereal import log
  monkeypatch.setattr(hyundaicanfd, 'Params', lambda: SimpleNamespace(get_int=lambda key: 0, get=lambda key: '0'))
  packer = CANPacker('hyundai_canfd_generated')
  definition = packer.dbc.name_to_msg['ADRV_0x161']
  stock = {key: 0 for key in definition.sigs}
  stock['COUNTER'] = 17
  original = stock.copy()
  model = log.ModelDataV2.new_message()
  model.meta.desire = desire
  state = SimpleNamespace(
    adrv_0x161=stock, out=structs.CarState(), modelV2=model, lfahda_cluster=None,
    cruise_buttons_msg=None, adrv_0x200=None, adrv_0x1ea=None, ccnc_0x162=None,
    is_metric=True, paddle_button_prev=0, softHoldActive=0, trailer_connected=False,
  )
  control = structs.CarControl(latActive=lat_active, enabled=True)

  def messages():
    return hyundaicanfd.create_ccnc_messages(
      SimpleNamespace(flags=HyundaiFlags.CAMERA_SCC), CANPacker('hyundai_canfd_generated'),
      SimpleNamespace(ECAN=0, CAM=2), 5, control, state, control.hudControl, 0, False, False, 0, False, 0, 0)
  actual = messages()
  monkeypatch.setattr(hyundaicanfd, '_select_cluster_background',
                      lambda enabled, lat, paddle, mode, **kwargs: 6 if mode > 0 and paddle else 1 if enabled else 3 if lat else 7)
  baseline = messages()
  assert len(actual) == len(baseline) == 1
  assert (actual[0][0], actual[0][2]) == (baseline[0][0], baseline[0][2]) == (0x161, 0)

  def decode(message):
    return {key: get_raw_value(message[1], sig) for key, sig in definition.sigs.items()}
  values, old = decode(actual[0]), decode(baseline[0])
  assert values['BACKGROUND'] == (6 if lat_active and desire in (1, 2) else 1)
  assert {k: v for k, v in values.items() if k not in ('BACKGROUND', 'CHECKSUM')} == {
    k: v for k, v in old.items() if k not in ('BACKGROUND', 'CHECKSUM')}
  assert values['CHECKSUM'] == hyundaicanfd.hkg_can_fd_checksum(0x161, None, bytearray(actual[0][1]))
  assert stock == original


@pytest.mark.parametrize("distance", (0.0, 1.6, 14.0, 14.1, 20.0, 25.5))
@pytest.mark.parametrize(("message", "detect", "expected_corner", "expected_front"), [
  *(('ADRV_0x1ea', detect, expected, None) for detect, expected in (
    (0, 0), (1, 1), (2, 2), (3, 3), (4, 1), (5, 1), (6, 1), (7, 1),
  )),
  *(('CCNC_0x162', detect, 3, expected) for detect, expected in (
    (1, 3), (2, 4), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7),
    (8, 8), (9, 9), (10, 10), (11, 11), (12, 12), (13, 13), (14, 14),
  )),
  # EV5 supplies nonzero corner geometry while 0x162 DETECT stays hidden.
  ('CCNC_0x162', 0, 3, 0),
])
def test_cluster_objects_restore_corner_state_without_blinking_or_distance_clamp(monkeypatch, message, distance, detect,
                                                                               expected_corner, expected_front):
  monkeypatch.setattr(hyundaicanfd, "Params", lambda: SimpleNamespace(get_int=lambda key: 0))
  packer = CANPacker("hyundai_canfd_generated")
  display_types = CANDefine("hyundai_canfd_generated").dv[message]
  definition = packer.dbc.name_to_msg[message]
  source = {key: 0 for key in definition.sigs}
  for side in ("LF", "RF", "LR", "RR"):
    source[f"{side}_DETECT"] = detect
    source[f"{side}_DETECT_DISTANCE"] = distance
    source[f"{side}_DETECT_LATERAL"] = 2.9
  if message == "CCNC_0x162":
    source.update(FF_DETECT=detect, FF_DISTANCE=81.2, FF_LATERAL=1.3,
                  FF_DETECT_ALT=2, FF_DISTANCE_ALT=42.1, FF_LATERAL_ALT=0.7)
  original = copy.deepcopy(source)
  state = SimpleNamespace(
    out=SimpleNamespace(brakeHoldActive=False, parkingBrake=False, steeringAngleDeg=6.0,
                        leftBlinker=False, rightBlinker=False),
    modelV2=None, lfahda_cluster=None, cruise_buttons_msg=None, adrv_0x161=None, adrv_0x200=None,
    adrv_0x1ea=source if message == "ADRV_0x1ea" else None,
    ccnc_0x162=source if message == "CCNC_0x162" else None,
    radarState=SimpleNamespace(leadOne=SimpleNamespace(status=True, dRel=81.2, yRel=-1.3, vRel=-5.0)),
  )
  cp = SimpleNamespace(flags=HyundaiFlags.CAMERA_SCC.value)
  can = SimpleNamespace(ECAN=0, CAM=2)
  control = SimpleNamespace(latActive=True, enabled=True)
  # FF uses radarState directly, independently of the older HUD distance.
  hud = SimpleNamespace(leadDistance=123.4, leadRadar=1, leadRelSpeed=-5.0)

  for frame in (0, 5, 65, 70, 100, 135, 200):
    messages = hyundaicanfd.create_ccnc_messages(cp, packer, can, frame, control, state, hud,
                                                0, False, False, 0, False, 0, 0)
    assert len(messages) == 1
    address, data, bus = messages[0]
    assert (address, bus) == (definition.address, 0)
    decoded = {key: get_raw_value(data, sig) * sig.factor + sig.offset for key, sig in definition.sigs.items()}
    assert decoded["CHECKSUM"] == hyundaicanfd.hkg_can_fd_checksum(address, None, bytearray(data))
    for side in ("LF", "RF", "LR", "RR"):
      assert decoded[f"{side}_DETECT_DISTANCE"] == pytest.approx(distance)
      assert decoded[f"{side}_DETECT_LATERAL"] == pytest.approx(2.9)
      box_at_zero = message == "CCNC_0x162" and detect in (1, 2)  # boxes become a gray car even without distance
      assert decoded[f"{side}_DETECT"] == (expected_corner if distance != 0 else 3 if box_at_zero else detect)
      if message == "CCNC_0x162" and distance != 0:
        assert display_types[f"{side}_DETECT"][decoded[f"{side}_DETECT"]] == "GRAY_CAR"
    if message == "CCNC_0x162":
      assert decoded["FF_DETECT"] == (expected_front or 4)
      for key in ("FF_DISTANCE", "FF_LATERAL", "FF_DETECT_ALT", "FF_DISTANCE_ALT", "FF_LATERAL_ALT"):
        assert decoded[key] == pytest.approx(original[key])
    else:
      assert decoded["LANELINE_CURVATURE"] == 2
    assert source == original


def test_hdp_gap_bars_and_popup(monkeypatch):
  from openpilot.cereal import log
  monkeypatch.setattr(hyundaicanfd, 'Params', lambda: SimpleNamespace(
    get_int=lambda key: 0, get=lambda key: '2' if key == 'HDPuse' else '0'))
  for attr in ('_gap_bars', '_gap_popup_until'):
    monkeypatch.delattr(hyundaicanfd.create_ccnc_messages, attr, raising=False)
  packer = CANPacker('hyundai_canfd_generated')
  definition = packer.dbc.name_to_msg['ADRV_0x161']
  state = SimpleNamespace(
    adrv_0x161={key: 0 for key in definition.sigs}, out=structs.CarState(), modelV2=log.ModelDataV2.new_message(),
    lfahda_cluster=None, cruise_buttons_msg=None, adrv_0x200=None, adrv_0x1ea=None, ccnc_0x162=None,
    is_metric=True, paddle_button_prev=0, softHoldActive=0, trailer_connected=False,
  )
  control = structs.CarControl(latActive=True, enabled=True)

  def send(frame, bars):
    control.hudControl.leadDistanceBars = bars
    msg = hyundaicanfd.create_ccnc_messages(
      SimpleNamespace(flags=HyundaiFlags.CAMERA_SCC), packer, SimpleNamespace(ECAN=0, CAM=2), frame, control, state,
      control.hudControl, 0, False, False, 0, False, 0, 0)[0]
    return {key: get_raw_value(msg[1], sig) for key, sig in definition.sigs.items()}

  first = send(5, 2)
  assert (first['DISTANCE'], first['ALERTS_3'], first['HDA_ICON']) == (2, 0, 5)  # HDP colors keep the real bars
  assert send(10, 3)['ALERTS_3'] == 9  # DISTANCE_3 popup after a change
  assert send(205, 3)['ALERTS_3'] == 9
  assert send(215, 3)['ALERTS_3'] == 0  # gone after 2 s
  assert first['DISTANCE_SPACING'] == 3 and send(300, 4)['DISTANCE_SPACING'] == 5  # 19-3 for gaps 1-3 only


@pytest.mark.parametrize(('standstill', 'lka', 'lca'), ((True, 4, 2), (False, 3, 0)))
def test_engaged_standstill_keeps_steering_and_lane_change_icons(monkeypatch, standstill, lka, lca):
  from openpilot.cereal import log
  monkeypatch.setattr(hyundaicanfd, 'Params', lambda: SimpleNamespace(get_int=lambda key: 0, get=lambda key: '0'))
  packer = CANPacker('hyundai_canfd_generated')
  definition = packer.dbc.name_to_msg['ADRV_0x161']
  out = structs.CarState(standstill=standstill, latEnabled=True)
  state = SimpleNamespace(
    adrv_0x161={key: 0 for key in definition.sigs}, out=out, modelV2=log.ModelDataV2.new_message(),
    lfahda_cluster=None, cruise_buttons_msg=None, adrv_0x200=None, adrv_0x1ea=None, ccnc_0x162=None,
    is_metric=True, paddle_button_prev=0, softHoldActive=0, trailer_connected=False,
  )
  control = structs.CarControl(latActive=False, enabled=True)  # controlsd turns steering off at standstill
  msg = hyundaicanfd.create_ccnc_messages(
    SimpleNamespace(flags=HyundaiFlags.CAMERA_SCC), packer, SimpleNamespace(ECAN=0, CAM=2), 5, control, state,
    control.hudControl, 0, False, False, 0, False, 0, 0)[0]
  values = {key: get_raw_value(msg[1], sig) for key, sig in definition.sigs.items()}
  assert (values['LKA_ICON'], values['LFA_ICON'] > 1, values['LCA_LEFT_ICON'], values['LCA_RIGHT_ICON']) == (lka, standstill, lca, lca)


@pytest.mark.parametrize(('color', 'lane_line', 'expected'), (
  (6, 10, 10), (2, 10, 8), (6, 15, 10),  # white dashed / DLM inner dashed -> green or white dashed
  (2, 11, 2), (4, 10, 4), (6, 0, 6),     # solid line, orange warning, no lane info stay as they were
))
def test_dashed_lane_line_codes(color, lane_line, expected):
  for car in hyundaicanfd.DASHED_LANE_CARS:  # clusters seen drawing the dashed codes
    assert hyundaicanfd._dashed_lane_line(color, lane_line, car) == expected
  # an allow list: Ioniq 9 / EV9 drew nothing for them, unchecked clusters keep the solid colour
  for car in (CAR.HYUNDAI_IONIQ_9, CAR.KIA_EV9, CAR.HYUNDAI_IONIQ_6, None):
    assert hyundaicanfd._dashed_lane_line(color, lane_line, car) == color


@pytest.mark.parametrize(('blindspot', 'left'), ((False, 14), (True, 4)))  # orange (BSD) stays even when unseen
@pytest.mark.parametrize(('display', 'car'), ((1, None), (1, CAR.HYUNDAI_IONIQ_5_PE), (0, CAR.HYUNDAI_IONIQ_5_PE),
                                              (1, CAR.HYUNDAI_IONIQ_9), (1, CAR.KIA_EV9)))
def test_unseen_lane_lines_send_14(monkeypatch, blindspot, left, display, car):
  from openpilot.cereal import log
  monkeypatch.setattr(hyundaicanfd, 'Params', cluster_params(display=display))
  packer = CANPacker('hyundai_canfd_generated')
  definition = packer.dbc.name_to_msg['ADRV_0x161']
  state = SimpleNamespace(
    adrv_0x161={key: 0 for key in definition.sigs}, out=structs.CarState(leftBlindspot=blindspot), modelV2=log.ModelDataV2.new_message(),
    lfahda_cluster=None, cruise_buttons_msg=None, adrv_0x200=None, adrv_0x1ea=None, ccnc_0x162=None,
    is_metric=True, paddle_button_prev=0, softHoldActive=0, trailer_connected=False,
  )
  control = structs.CarControl(latActive=True, enabled=True)
  control.hudControl.rightLaneVisible = True
  msg = hyundaicanfd.create_ccnc_messages(
    SimpleNamespace(flags=HyundaiFlags.CAMERA_SCC, carFingerprint=car), packer, SimpleNamespace(ECAN=0, CAM=2), 5, control, state,
    control.hudControl, 0, False, False, 0, False, 0, 0)[0]
  values = {key: get_raw_value(msg[1], sig) for key, sig in definition.sigs.items()}
  wip = not display or car in (CAR.HYUNDAI_IONIQ_9, CAR.KIA_EV9)  # carrot-wip: an unseen line is 0, orange or not
  assert (values['LANELINE_LEFT'], values['LANELINE_RIGHT']) == (0 if wip else left, 2)


@pytest.mark.parametrize(('lane_change', 'camera', 'expected'), (('off', 10, 8), ('laneChangeStarting', 10, 8), ('off', 0, 14)))
def test_lane_hidden_only_when_model_and_camera_miss(monkeypatch, lane_change, camera, expected):
  # the model has already hidden the line (probs 0.01 for 1 s); a camera lane keeps it shown
  from openpilot.cereal import log
  monkeypatch.setattr(hyundaicanfd, 'Params', cluster_params(display=1))
  monkeypatch.setitem(hyundaicanfd.create_ccnc_messages.__dict__, '_lane_unseen', {'L': (True, 0), 'R': (True, 0)})
  packer = CANPacker('hyundai_canfd_generated')
  definition = packer.dbc.name_to_msg['ADRV_0x161']
  md = log.ModelDataV2.new_message()
  md.laneLineProbs = [0.01] * 4
  md.meta.laneChangeState = lane_change
  state = SimpleNamespace(
    adrv_0x161={key: 0 for key in definition.sigs}, out=structs.CarState(leftLaneLine=camera, rightLaneLine=camera), modelV2=md,
    lfahda_cluster=None, cruise_buttons_msg=None, adrv_0x200=None, adrv_0x1ea=None, ccnc_0x162=None,
    is_metric=True, paddle_button_prev=0, softHoldActive=0, trailer_connected=False,
  )
  control = structs.CarControl(latActive=True, enabled=True)
  control.hudControl.leftLaneVisible = control.hudControl.rightLaneVisible = True
  msg = hyundaicanfd.create_ccnc_messages(
    SimpleNamespace(flags=HyundaiFlags.CAMERA_SCC, carFingerprint=CAR.HYUNDAI_IONIQ_5_PE), packer, SimpleNamespace(ECAN=0, CAM=2), 5, control, state,
    control.hudControl, 0, False, False, 0, False, 0, 0)[0]
  assert get_raw_value(msg[1], definition.sigs['LANELINE_LEFT']) == expected
  assert get_raw_value(msg[1], definition.sigs['LANELINE_RIGHT']) == expected


def test_lane_unseen_hysteresis():
  state = {}
  assert not hyundaicanfd._lane_unseen(state, 'L', 0.02, 0)
  assert not hyundaicanfd._lane_unseen(state, 'L', 0.02, 95)   # parking lot, under 1 s
  assert hyundaicanfd._lane_unseen(state, 'L', 0.02, 100)      # hidden after 1 s
  assert hyundaicanfd._lane_unseen(state, 'L', 0.10, 120)      # between thresholds keeps it hidden
  assert not hyundaicanfd._lane_unseen(state, 'L', 0.13, 125)  # city stop level shows it again
  assert not hyundaicanfd._lane_unseen(state, 'L', 0.05, 130)
  assert not hyundaicanfd._lane_unseen(state, 'L', 0.10, 200)  # a dip that does not last 1 s resets
  assert not hyundaicanfd._lane_unseen(state, 'L', 0.05, 205)
  assert not hyundaicanfd._lane_unseen(state, 'R', 0.02, 205)  # sides are independent


@pytest.mark.parametrize("traffic_state, expected", [(0, 1), (1, 5), (2, 8)])
def test_traffic_light_background(traffic_state, expected):
  # turning (6) is overridden too while a light is detected
  assert _select_cluster_background(True, True, False, 0, traffic_state=traffic_state) == expected
  assert _select_cluster_background(True, True, False, 0, turning=True, traffic_state=traffic_state) == (6 if traffic_state == 0 else expected)


def test_traffic_green_shown_only_two_seconds():
  _traffic_display_state.last, _traffic_display_state.green_until = 0, 0
  assert _traffic_display_state(1, 0) == 1      # red stays
  assert _traffic_display_state(1, 500) == 1
  assert _traffic_display_state(2, 1000) == 2   # turned green
  assert _traffic_display_state(2, 1199) == 2
  assert _traffic_display_state(2, 1200) == 0   # 2 s later: back to normal
  assert _traffic_display_state(0, 1300) == 0
  assert _traffic_display_state(2, 1400) == 2   # a new green shows again


@pytest.mark.parametrize(('lat_hud', 'desire', 'color'), ((0, 0, 0), (1, 0, 1), (2, 0, 3), (3, 0, 4), (4, 0, 5), (4, 3, 1), (2, 4, 1), (0, 3, 0)))
@pytest.mark.parametrize('left_visible', (True, False))
@pytest.mark.parametrize('display', (0, 1))
def test_lane_highlight_follows_lateral_state(monkeypatch, lat_hud, desire, color, left_visible, display):
  from openpilot.cereal import log
  monkeypatch.setattr(hyundaicanfd, 'Params', cluster_params(display=display))
  packer = CANPacker('hyundai_canfd_generated')
  definition = packer.dbc.name_to_msg['ADRV_0x161']
  state = SimpleNamespace(
    adrv_0x161={key: 0 for key in definition.sigs}, out=structs.CarState(), modelV2=log.ModelDataV2.new_message(),
    lfahda_cluster=None, cruise_buttons_msg=None, adrv_0x200=None, adrv_0x1ea=None, ccnc_0x162=None,
    is_metric=True, paddle_button_prev=0, softHoldActive=0, trailer_connected=False,
  )
  control = structs.CarControl(latActive=lat_hud > 0, enabled=True)
  control.hudControl.latHudState = lat_hud
  state.modelV2.meta.desire = desire  # lane change takes priority
  control.hudControl.leftLaneVisible, control.hudControl.rightLaneVisible = left_visible, True
  color = color if left_visible and display else 0  # a hidden lane line (14) or the key off: stock value kept
  msg = hyundaicanfd.create_ccnc_messages(
    SimpleNamespace(flags=HyundaiFlags.CAMERA_SCC), packer, SimpleNamespace(ECAN=0, CAM=2), 5, control, state,
    control.hudControl, 0, False, False, 0, False, 0, 0)[0]
  assert get_raw_value(msg[1], definition.sigs['LANE_HIGHLIGHT']) == color  # 0: stock value kept
  assert get_raw_value(msg[1], definition.sigs['LANE_HIGHLIGHT_DISTANCE']) == 0


@pytest.mark.parametrize(('display', 'enabled', 'desired', 'expected'), (
  (1, True, 40.0, 400), (1, True, 0.0, 573), (1, False, 40.0, 573),
  (0, True, 40.0, 0),  # key off: carrot-wip writes the lead distance (no lead here: 0)
))
def test_target_ring_marks_the_target_gap(monkeypatch, display, enabled, desired, expected):
  # engaged: openpilot's desired distance; otherwise (or without one) the stock target gap stays
  from openpilot.cereal import log
  monkeypatch.setattr(hyundaicanfd, 'Params', cluster_params(display=display))
  packer = CANPacker('hyundai_canfd_generated')
  definition = packer.dbc.name_to_msg['ADRV_0x161']
  stock = {key: 0 for key in definition.sigs}
  stock['TARGET_DISTANCE'] = 57.3
  state = SimpleNamespace(
    adrv_0x161=stock, out=structs.CarState(), modelV2=log.ModelDataV2.new_message(),
    lfahda_cluster=None, cruise_buttons_msg=None, adrv_0x200=None, adrv_0x1ea=None, ccnc_0x162=None,
    is_metric=True, paddle_button_prev=0, softHoldActive=0, trailer_connected=False,
  )
  control = structs.CarControl(latActive=True, enabled=enabled)
  control.hudControl.desiredDistance = desired
  msg = hyundaicanfd.create_ccnc_messages(
    SimpleNamespace(flags=HyundaiFlags.CAMERA_SCC), packer, SimpleNamespace(ECAN=0, CAM=2), 5, control, state,
    control.hudControl, 0, False, False, 0, False, 0, 0)[0]
  assert get_raw_value(msg[1], definition.sigs['TARGET_DISTANCE']) == expected


@pytest.mark.parametrize(("car", "enabled", "lat_active", "display", "expected"), (
  ("HYUNDAI_IONIQ_5_PE", True, False, 1, 1),   # cruise engaged
  ("HYUNDAI_IONIQ_5_PE", False, True, 1, 1),   # steering only
  ("HYUNDAI_IONIQ_5_PE", False, False, 1, 0),
  ("HYUNDAI_IONIQ_5_PE", True, True, 0, 0),    # key off: icon bit not set, as in carrot-wip
  ("HYUNDAI_AZERA_7TH_GEN", True, True, 1, 1),  # GN7 / EV4: owner report 11-12
  ("KIA_EV4", True, True, 1, 1),
  ("KIA_EV9", True, True, 1, 0),               # bit 188 unchecked on EV9
))
def test_hdp_icon_while_engaged(monkeypatch, car, enabled, lat_active, display, expected):
  monkeypatch.setattr(hyundaicanfd, "Params", cluster_params(display=display))
  packer = CANPacker("hyundai_canfd_generated")
  definition = packer.dbc.name_to_msg["CCNC_0x162"]
  state = SimpleNamespace(
    out=SimpleNamespace(brakeHoldActive=False, parkingBrake=False, steeringAngleDeg=0.0, leftBlinker=False, rightBlinker=False),
    modelV2=None, lfahda_cluster=None, cruise_buttons_msg=None, adrv_0x161=None, adrv_0x200=None, adrv_0x1ea=None,
    ccnc_0x162={key: 0 for key in definition.sigs}, radarState=None,
  )
  cp = SimpleNamespace(flags=HyundaiFlags.CAMERA_SCC.value, carFingerprint=getattr(hyundaicanfd.CAR, car))
  control = SimpleNamespace(latActive=lat_active, enabled=enabled)
  hud = SimpleNamespace(leadDistance=0, leadRadar=0, leadRelSpeed=0)
  (address, data, bus), = hyundaicanfd.create_ccnc_messages(cp, packer, SimpleNamespace(ECAN=0, CAM=2), 0, control, state, hud,
                                                            0, False, False, 0, False, 0, 0)
  assert (data[hyundaicanfd.HDP_ICON_BIT // 8] >> (hyundaicanfd.HDP_ICON_BIT % 8)) & 1 == expected
  assert get_raw_value(data, definition.sigs['CHECKSUM']) == hyundaicanfd.hkg_can_fd_checksum(address, None, bytearray(data))


@pytest.mark.parametrize("car", ("HYUNDAI_IONIQ_5_PE", "HYUNDAI_IONIQ_9", "KIA_EV9"))  # DBC values: every CCNC cluster
@pytest.mark.parametrize("display", (0, 1))
def test_engage_and_disengage_popups(monkeypatch, car, display):
  from openpilot.cereal import log
  monkeypatch.setattr(hyundaicanfd, 'Params', cluster_params(display=display))
  for attr in ('_was_enabled', '_engage_popup'):
    monkeypatch.delattr(hyundaicanfd.create_ccnc_messages, attr, raising=False)
  packer = CANPacker('hyundai_canfd_generated')
  definition = packer.dbc.name_to_msg['ADRV_0x161']
  state = SimpleNamespace(
    adrv_0x161={key: 0 for key in definition.sigs}, out=structs.CarState(latEnabled=True), modelV2=log.ModelDataV2.new_message(),
    lfahda_cluster=None, cruise_buttons_msg=None, adrv_0x200=None, adrv_0x1ea=None, ccnc_0x162=None,
    is_metric=True, paddle_button_prev=0, softHoldActive=0, trailer_connected=False,
  )
  cp = SimpleNamespace(flags=HyundaiFlags.CAMERA_SCC, carFingerprint=getattr(hyundaicanfd.CAR, car))

  def alerts_5(frame, enabled):
    control = structs.CarControl(latActive=enabled, enabled=enabled)
    msg = hyundaicanfd.create_ccnc_messages(cp, packer, SimpleNamespace(ECAN=0, CAM=2), frame, control, state,
                                            control.hudControl, 0, False, False, 0, False, 0, 0)[0]
    return get_raw_value(msg[1], definition.sigs['ALERTS_5'])

  assert alerts_5(0, False) == 0
  assert [alerts_5(f, True) for f in (100, 295, 300)] == ([19, 19, 0] if display else [0, 0, 0])   # engage: 2 s
  assert [alerts_5(f, False) for f in (500, 695, 700)] == ([21, 21, 0] if display else [0, 0, 0])  # disengage: 2 s


@pytest.mark.parametrize(("car", "alert_type", "enabled", "field", "expected"), (
  ("HYUNDAI_IONIQ_5_PE", "speedTooHigh/warning", True, "ALERTS_4", 83),
  ("HYUNDAI_IONIQ_5_PE", "steerUnavailable/immediateDisable", False, "ALERTS_5", 9),   # beats the disengage popup (21)
  ("HYUNDAI_IONIQ_5_PE", "canError/immediateDisable", False, "ALERTS_4", 147),
  ("HYUNDAI_IONIQ_5_PE", "reverseGear/userDisable", False, "ALERTS_4", 0),             # not mirrored (user 11-13)
  ("HYUNDAI_IONIQ_5_PE", "reverseGear/permanent", False, "ALERTS_4", 0),               # just parked in R
  ("HYUNDAI_IONIQ_5_PE", "driverDistracted3/permanent", True, "ALERTS_4", 0),          # DM is left alone
  ("KIA_EV9", "canError/immediateDisable", False, "ALERTS_4", 147),                    # DBC value: every cluster
  ("KIA_EV9", "steerUnavailable/immediateDisable", False, "ALERTS_5", 21),             # 9 is not in the DBC: popup stays
  ("KIA_EV4", "steerUnavailable/immediateDisable", False, "ALERTS_5", 9),              # owner report 11-12
  ("HYUNDAI_IONIQ_5_PE", "steerSaturated/warning", True, "ALERTS_3", 18),              # comma "take control" synced
  ("KIA_EV9", "steerSaturated/warning", True, "ALERTS_3", 18),                       # DBC value: every cluster
))
def test_openpilot_alerts_map_to_cluster_texts(monkeypatch, car, alert_type, enabled, field, expected):
  from openpilot.cereal import log
  monkeypatch.setattr(hyundaicanfd, 'Params', cluster_params(display=1))
  for attr in ('_was_enabled', '_engage_popup'):
    monkeypatch.delattr(hyundaicanfd.create_ccnc_messages, attr, raising=False)
  packer = CANPacker('hyundai_canfd_generated')
  definition = packer.dbc.name_to_msg['ADRV_0x161']
  state = SimpleNamespace(
    adrv_0x161={key: 0 for key in definition.sigs}, out=structs.CarState(latEnabled=True), modelV2=log.ModelDataV2.new_message(),
    lfahda_cluster=None, cruise_buttons_msg=None, adrv_0x200=None, adrv_0x1ea=None, ccnc_0x162=None,
    is_metric=True, paddle_button_prev=0, softHoldActive=0, trailer_connected=False,
  )
  cp = SimpleNamespace(flags=HyundaiFlags.CAMERA_SCC, carFingerprint=getattr(hyundaicanfd.CAR, car))
  for frame, en, alert in ((0, True, ""), (100, enabled, alert_type)):  # second frame: disengaged here if not enabled
    control = structs.CarControl(latActive=en, enabled=en)
    control.hudControl.alertType = alert
    msg = hyundaicanfd.create_ccnc_messages(cp, packer, SimpleNamespace(ECAN=0, CAM=2), frame, control, state,
                                            control.hudControl, 0, False, False, 0, False, 0, 0)[0]
  assert get_raw_value(msg[1], definition.sigs[field]) == expected


def test_sharp_turn_text_beats_gap_popup_and_chimes_once(monkeypatch):
  from openpilot.cereal import log
  monkeypatch.setattr(hyundaicanfd, 'Params', cluster_params(display=1, hdp='2'))
  for attr in ('_was_enabled', '_engage_popup', '_gap_bars', '_gap_popup_until', '_chime_shown', '_chime_until'):
    monkeypatch.delattr(hyundaicanfd.create_ccnc_messages, attr, raising=False)
  packer = CANPacker('hyundai_canfd_generated')
  definition = packer.dbc.name_to_msg['ADRV_0x161']
  stock = {key: 0 for key in definition.sigs}
  state = SimpleNamespace(
    adrv_0x161=stock, out=structs.CarState(latEnabled=True), modelV2=log.ModelDataV2.new_message(),
    lfahda_cluster=None, cruise_buttons_msg=None, adrv_0x200=None, adrv_0x1ea=None, ccnc_0x162=None,
    is_metric=True, paddle_button_prev=0, softHoldActive=0, trailer_connected=False,
  )
  cp = SimpleNamespace(flags=HyundaiFlags.CAMERA_SCC, carFingerprint=hyundaicanfd.CAR.HYUNDAI_IONIQ_5_PE)

  def send(frame, alert, bars=3, alerts_1=0):
    stock['ALERTS_1'] = alerts_1
    control = structs.CarControl(latActive=True, enabled=True)
    control.hudControl.alertType = alert
    control.hudControl.leadDistanceBars = bars
    msg = hyundaicanfd.create_ccnc_messages(cp, packer, SimpleNamespace(ECAN=0, CAM=2), frame, control, state,
                                            control.hudControl, 0, False, False, 0, False, 0, 0)[0]
    return get_raw_value(msg[1], definition.sigs['ALERTS_3']), get_raw_value(msg[1], definition.sigs['SOUNDS_4'])

  assert send(0, "", bars=2) == (0, 0)
  assert send(5, "") == (9, 0)                                    # HDP gap popup (DISTANCE_3)
  assert send(10, "steerSaturated/warning") == (18, 2)          # the alert beats the popup; double chime
  assert send(105, "steerSaturated/warning") == (18, 2)
  assert send(110, "steerSaturated/warning") == (18, 0)         # chime ~1 s, text stays
  assert send(115, "") == (9, 0)                                  # popup back once the alert ends
  assert send(300, "steerSaturated/warning", alerts_1=11) == (18, 0)  # stock emergency owns the sound
  stock['ALERTS_3'] = 21                                          # a stock text wins
  assert send(500, "steerSaturated/warning") == (21, 0)


def test_dbc_listed_split_matches_the_gates():
  # popups and DBC-named texts go to every CCNC cluster; cluster-test-only values stay gated by NON_DBC_CLUSTER_VALUE_CARS
  assert hyundaicanfd._dbc_listed("ALERTS_5", hyundaicanfd.ENGAGE_POPUP) and hyundaicanfd._dbc_listed("ALERTS_5", hyundaicanfd.DISENGAGE_POPUP)
  assert hyundaicanfd._dbc_listed("ALERTS_3", 18)  # CHECK_SURROUNDINGS
  assert not hyundaicanfd._dbc_listed("ALERTS_5", 9)


@pytest.mark.parametrize("traffic", (0, 1))
def test_traffic_background_needs_its_key(monkeypatch, traffic):
  # CcncTrafficBackground 0: the red light leaves carrot-wip's engaged background (1); 1: steady red (5)
  from openpilot.cereal import log
  monkeypatch.setattr(hyundaicanfd, 'Params', cluster_params(traffic=traffic))
  _traffic_display_state.last, _traffic_display_state.green_until = 0, 0
  packer = CANPacker('hyundai_canfd_generated')
  definition = packer.dbc.name_to_msg['ADRV_0x161']
  state = SimpleNamespace(
    adrv_0x161={key: 0 for key in definition.sigs}, out=structs.CarState(), modelV2=log.ModelDataV2.new_message(),
    lfahda_cluster=None, cruise_buttons_msg=None, adrv_0x200=None, adrv_0x1ea=None, ccnc_0x162=None,
    is_metric=True, paddle_button_prev=0, softHoldActive=0, trailer_connected=False,
  )
  control = structs.CarControl(latActive=True, enabled=True)
  control.hudControl.trafficState = 1
  msg = hyundaicanfd.create_ccnc_messages(
    SimpleNamespace(flags=HyundaiFlags.CAMERA_SCC), packer, SimpleNamespace(ECAN=0, CAM=2), 5, control, state,
    control.hudControl, 0, False, False, 0, False, 0, 0)[0]
  assert get_raw_value(msg[1], definition.sigs['BACKGROUND']) == (5 if traffic else 1)

@pytest.mark.parametrize("age,visible", [(0, True), (150_000_000, True), (150_000_001, False), (-1, False)])
def test_ev6_non_camera_scc_hidden_corner_packet(age, visible):
  name = "ADRV_0x1ea"
  source = {}
  for side, kind, distance in [("LF", 4, 12.3), ("RF", 2, 5.2), ("LR", 0, 7), ("RR", 4, 0)]:
    source.update({f"{side}_DETECT": kind, f"{side}_DETECT_DISTANCE": distance, f"{side}_DETECT_LATERAL": 1.2})
  parser = SimpleNamespace(ts_nanos={name: {"COUNTER": 100}}, _last_update_nanos=100+age,
                           dat={0x1EA: bytes(32)}, vl={name: source})
  cp = SimpleNamespace(flags=HyundaiFlags.CANFD_HDA2, carFingerprint=hyundaicanfd.CAR.KIA_EV6)
  def packet(cam):
    packer = CANPacker("hyundai_canfd_generated")
    msgs = hyundaicanfd.create_adrv_messages(cp, packer, SimpleNamespace(ECAN=1), 5, cam)
    assert len(msgs) == 2
    addr, data, bus = msgs[0]
    assert (addr, bus) == (0x1EA, 1)
    return {k: get_raw_value(data, sig) * sig.factor + sig.offset for k, sig in packer.dbc.name_to_msg[name].sigs.items()}
  expected = packet(None)
  if visible:
    expected.update(LF_DETECT=1, RF_DETECT=2, LF_DETECT_DISTANCE=12.3, RF_DETECT_DISTANCE=5.2,
                    LF_DETECT_LATERAL=1.2, RF_DETECT_LATERAL=1.2)
  actual = packet(parser)
  del actual["CHECKSUM"], expected["CHECKSUM"]
  assert actual == pytest.approx(expected)



def test_ev6_adas_display_uses_physical_ecan_rx():
  name = "ADRV_0x1ea"
  dbc = "hyundai_canfd_generated"
  parser = CANParser(dbc, [], 1)
  parser._add_message(name, float("nan"), ignore_counter=True)
  packer = CANPacker(dbc)
  addr, data, _ = packer.make_can_msg(name, 1, {"RF_DETECT": 4, "RF_DETECT_DISTANCE": 9.5, "RF_DETECT_LATERAL": 1.2})
  for bus in (129, 193, 2):
    parser.update([100, [(addr, data, bus)]])
    assert not hyundaicanfd.ev6_cluster_corners(parser)
  parser.update([101, [(addr, data, 1)]])
  assert hyundaicanfd.ev6_cluster_corners(parser) == pytest.approx({
    "RF_DETECT": 1, "RF_DETECT_DISTANCE": 9.5, "RF_DETECT_LATERAL": 1.2})
  parser.update([150_000_102, [(addr, data, 129)]])
  assert not hyundaicanfd.ev6_cluster_corners(parser)

@pytest.mark.parametrize("age,fault,expected", [(100_000_000, False, 1), (250_000_001, False, 0), (0, True, 0)])
def test_ev6_adas_neighbor_fallback(age, fault, expected):
  packer = CANPacker("hyundai_canfd_generated")
  stamp = 1_000_000_000
  source = {"HDA_MODE2": 5, "AUTOLANECHANGE_MSG": 8, "LANE_LEFT": 1, "LANE_RIGHT": 0, "LANE_CHANGING": 1}
  for side in ("LF", "RF", "LR", "RR"):
    source.update({f"{side}_DETECT": 2 if side == "LF" else 0,
                   f"{side}_DETECT_DISTANCE": 9, f"{side}_DETECT_LATERAL": 2})
  parser = SimpleNamespace(ts_nanos={"ADRV_0x1ea": {"COUNTER": stamp}}, _last_update_nanos=stamp,
                           dat={0x1EA: bytes(32)}, vl={"ADRV_0x1ea": source})
  def lead(d, y):
    return SimpleNamespace(status=True, radar=True, dRel=d, yRel=y)
  radar = SimpleNamespace(mdMonoTime=stamp, leadsLeft=[lead(3, 3)], leadsRight=[lead(1, 3), lead(24, -3), lead(7, -2)],
                          radarErrors=SimpleNamespace(canError=fault, radarFault=False, wrongConfig=False, radarUnavailableTemporary=False))
  cp = SimpleNamespace(flags=HyundaiFlags.CANFD_HDA2, carFingerprint=hyundaicanfd.CAR.KIA_EV6)
  msg = hyundaicanfd.create_adrv_messages(cp, packer, SimpleNamespace(ECAN=1), 5, parser, radar=radar, now_nanos=stamp+age)[0]
  values = {k: get_raw_value(msg[1], sig) * sig.factor + sig.offset for k, sig in packer.dbc.name_to_msg["ADRV_0x1ea"].sigs.items()}
  assert (values["HDA_MODE2"], values["AUTOLANECHANGE_MSG"]) == (5, 8)
  assert (values["LANE_LEFT"], values["LANE_RIGHT"], values["LANE_CHANGING"]) == (1, 0, 1)
  assert (values["LF_DETECT"], values["LF_DETECT_DISTANCE"]) == (2, 9)
  assert (values["RF_DETECT"], values["RF_DETECT_DISTANCE"], values["RF_DETECT_LATERAL"]) == (expected, 7*expected, 2*expected)
  assert values["LR_DETECT"] == values["RR_DETECT"] == 0


@pytest.mark.parametrize("target, offset, age, occupied, expected", [
  (-3.5, 0, 100, False, "LF"), (3.5, 0, 100, False, "RF"),
  (-3.5, -3.5, 100, False, None), (-3.5, 0, 250_000_001, False, None),
  (-3.5, 0, 100, True, None), (-1.8, 0, 100, False, None),
])
def test_ev6_vision_only_neighbor(target, offset, age, occupied, expected):
  stamp = 1_000_000_000
  model = SimpleNamespace(timestampEof=stamp, leadsV3=[SimpleNamespace(prob=.9, x=[20], y=[target], yStd=[.25])],
                          laneLineProbs=[.9]*4, laneLines=[SimpleNamespace(x=[0, 20], y=[y, y+offset]) for y in (-5.25, -1.75, 1.75, 5.25)])
  values = {"LF_DETECT": 2} if occupied else {}
  previous = values.copy()
  hyundaicanfd._add_ev6_vision_neighbor(values, model, stamp+age)
  if expected:
    assert values == pytest.approx({f"{expected}_DETECT": 1, f"{expected}_DETECT_DISTANCE": 18.48,
                                    f"{expected}_DETECT_LATERAL": 3.5})
  else:
    assert values == previous


@pytest.mark.parametrize("age,stock_mode", [(0, 0), (250_000_000, 1), (250_000_001, 1), (0, 3), (0, 5)])
def test_ev6_camera_scc_oem_icons(monkeypatch, age, stock_mode):
  from openpilot.cereal import log
  monkeypatch.setattr(hyundaicanfd, "Params", lambda: SimpleNamespace(get_int=lambda key: 0, get=lambda key: "2"))
  packer = CANPacker("hyundai_canfd_generated")
  def blank(name):
    return dict.fromkeys(packer.dbc.name_to_msg[name].sigs, 0)
  stamp = 1_000_000_000
  model = log.ModelDataV2.new_message(timestampEof=stamp)
  stock, corner = blank("ADRV_0x161"), blank("ADRV_0x1ea")
  stock.update(NAV_ICON=4, LCA_RIGHT_ICON=1, LCA_LEFT_ARROW=1)
  corner["HDA_MODE2"] = stock_mode
  cam = SimpleNamespace(ts_nanos={"ADRV_0x161":{"COUNTER":stamp}}, _last_update_nanos=stamp,
                        dat={0x161: bytes(32)}, vl={"ADRV_0x161":stock})
  state = SimpleNamespace(adrv_0x161=stock, adrv_0x1ea=corner, cp_cam=cam, modelV2=model, out=structs.CarState(leftBlinker=True),
                          lfahda_cluster=None, cruise_buttons_msg=None, adrv_0x200=None, ccnc_0x162=blank("CCNC_0x162"), scc_control=None,
                          is_metric=True, paddle_button_prev=0, softHoldActive=0, trailer_connected=False)
  control = structs.CarControl(latActive=True, enabled=True)
  control.hudControl.leftLaneVisible = control.hudControl.rightLaneVisible = True
  state.out.rightBlindspot = True
  radar = log.RadarState.new_message(mdMonoTime=stamp)
  radar.init("leadsRight", 1)
  lead = radar.leadsRight[0]
  lead.status, lead.radar, lead.dRel, lead.yRel = True, True, 12.0, -3.5
  corner.update(LR_DETECT=2, LR_DETECT_DISTANCE=8, LR_DETECT_LATERAL=3)
  cam.ts_nanos["ADRV_0x1ea"] = {"COUNTER": stamp}
  cam.dat[0x1ea] = bytes(32)
  cam.vl["ADRV_0x1ea"] = corner
  model.init("leadsV3", 1)
  target = model.leadsV3[0]
  target.prob, target.x, target.y, target.yStd = .95, [20], [0], [.2]
  model.laneLineProbs = [.9] * 4
  for line, offset in zip(model.init("laneLines", 4), (-5.25, -1.75, 1.75, 5.25)):
    line.x, line.y = [0, 30], [offset, offset]
  state.radarState = radar
  cp = SimpleNamespace(flags=HyundaiFlags.CAMERA_SCC | HyundaiFlags.CANFD_HDA2, carFingerprint=hyundaicanfd.CAR.KIA_EV6, openpilotLongitudinalControl=True)
  msgs = hyundaicanfd.create_ccnc_messages(cp, packer, SimpleNamespace(ECAN=0, CAM=2), 5, control, state, control.hudControl,
                                          0, False, False, 2, False, 0, 0, now_nanos=stamp+age)
  frames = {addr:data for addr,data,_ in msgs}
  def raw(addr,key):
    return get_raw_value(frames[addr], packer.dbc.addr_to_msg[addr].sigs[key])
  assert [raw(0x161,k) for k in ("NAV_ICON","LCA_RIGHT_ICON","LCA_LEFT_ARROW")] == [4,1,1]
  assert (raw(0x161, "LANELINE_LEFT"), raw(0x161, "LANELINE_RIGHT")) == (6, 4)
  assert raw(0x1ea,"HDA_MODE2") == stock_mode
  assert raw(0x162, "LR_DETECT") == (3 if age <= 150_000_000 else 0)
  assert raw(0x162, "RR_DETECT") == 0
  assert raw(0x162, "RF_DETECT") == (3 if age <= 250_000_000 else 0)
  assert raw(0x162, "FF_DETECT") == (3 if age <= 250_000_000 else 0)
  assert raw(0x1ea,"RF_DETECT") == int(age <= 250_000_000)

  # Check a factory notification, then its cancellation on the following frame.
  scene = state.ccnc_0x162
  cam.dat[0x162] = bytes(32)
  cam.vl["CCNC_0x162"] = scene
  for active in (1, 0):
    stamp += 50_000_000
    cam._last_update_nanos = stamp
    for name in ("CCNC_0x162", "ADRV_0x161"):
      cam.ts_nanos[name] = {"COUNTER": stamp}
    stock.update(ALERTS_3=21*active, ALERTS_5=11*active, SOUNDS_3=3*active, LANE_HIGHLIGHT=active)
    scene.update(FF_DETECT=7*active, FF_DISTANCE=20*active, FF_DETECT_ALT=3*active, FF_DISTANCE_ALT=35*active,
                 SIGNS=8*active, FAULT_HDA=active)
    msgs = hyundaicanfd.create_ccnc_messages(cp, packer, SimpleNamespace(ECAN=0, CAM=2), 10, control, state,
                                             control.hudControl, 0, False, False, 2, False, 0, 0, now_nanos=stamp)
    frames = {addr: data for addr, data, _ in msgs}
    for key in ("ALERTS_3", "ALERTS_5", "SOUNDS_3", "LANE_HIGHLIGHT"):
      assert raw(0x161, key) == stock[key]
    for key in ("SIGNS", "FF_DETECT_ALT", "FAULT_HDA"):
      assert raw(0x162, key) == scene[key]
    assert raw(0x162, "FF_DETECT") == (7 if active else 3)
    for enabled, elapsed, visible in ((True, 0, True), (False, 0, False), (True, 150_000_001, False)):
      scene.update(SIGNS=9, SPEEDLIMIT=60, SPEEDLIMIT_FLASH=2, SPEEDLIMIT_WEATHER=1)
      msgs = hyundaicanfd.create_ccnc_messages(cp, packer, SimpleNamespace(ECAN=0, CAM=2), 10, control, state,
        control.hudControl, 0, False, False, 2, False, 0, 0, now_nanos=stamp+elapsed, show_stock_signs=enabled)
      frames = {addr: data for addr, data, _ in msgs}
      for key in ("SIGNS", "SPEEDLIMIT", "SPEEDLIMIT_FLASH", "SPEEDLIMIT_WEATHER"):
        assert raw(0x162, key) == (scene[key] if visible else 0)




@pytest.mark.parametrize("age,kind,lateral,expected", [
  (0, 3, 3.5, True), (150_000_000, 6, 6.3, True), (150_000_001, 3, 3.5, False),
  (0, 0, 3.5, False), (0, 7, 3.5, False), (0, 3, 6.4, False),
])
def test_ev6_ccnc_corner_neighbors(age, kind, lateral, expected):
  stamp = 1_000_000_000
  source = dict(LF_DETECT=3, LF_DETECT_DISTANCE=40, LF_DETECT_LATERAL=3.5,
                RF_DETECT=6, RF_DETECT_DISTANCE=75, RF_DETECT_LATERAL=8,
                LR_DETECT=4, LR_DETECT_DISTANCE=8, LR_DETECT_LATERAL=4,
                RR_DETECT=kind, RR_DETECT_DISTANCE=5, RR_DETECT_LATERAL=lateral)
  cam = SimpleNamespace(ts_nanos={"CCNC_0x162": {"COUNTER": stamp}}, _last_update_nanos=stamp,
                        dat={0x162: bytes(32)}, vl={"CCNC_0x162": source})
  values = dict(LR_DETECT=2, LR_DETECT_DISTANCE=10, LR_DETECT_LATERAL=3)
  original = values.copy()
  hyundaicanfd._add_ev6_corner_neighbors(values, cam, stamp + age)
  if age <= 150_000_000:
    original.update(LF_DETECT=1, LF_DETECT_DISTANCE=40, LF_DETECT_LATERAL=3.5,
                    RF_DETECT=1, RF_DETECT_DISTANCE=75, RF_DETECT_LATERAL=8)
  if expected:
    original.update(RR_DETECT=1, RR_DETECT_DISTANCE=5, RR_DETECT_LATERAL=lateral)
  assert values == original

@pytest.mark.parametrize("side", ["L", "R"])
def test_ev6_passing_neighbor_positions(side):
  packer = CANPacker("hyundai_canfd_generated")
  name = "CCNC_0x162"
  parser = CANParser("hyundai_canfd_generated", [], 2)
  parser._add_message(name, float("nan"), ignore_counter=True)
  for i, (end, distance) in enumerate([("R", 12), ("R", 4), ("R", 0.5), ("F", 0.5), ("F", 4), ("F", 12)]):
    stamp = 1_000_000_000 + i * 50_000_000
    slot = side + end
    frame = packer.make_can_msg(name, 2, {f"{slot}_DETECT": 3, f"{slot}_DETECT_DISTANCE": distance,
                                          f"{slot}_DETECT_LATERAL": 3.5})
    parser.update([stamp, [frame]])
    values = {}
    hyundaicanfd._add_ev6_corner_neighbors(values, parser, stamp)
    assert values == pytest.approx({f"{slot}_DETECT": 1, f"{slot}_DETECT_DISTANCE": distance,
                                    f"{slot}_DETECT_LATERAL": 3.5})
