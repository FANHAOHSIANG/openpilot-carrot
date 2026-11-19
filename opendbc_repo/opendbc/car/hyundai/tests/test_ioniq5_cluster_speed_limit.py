import math
from types import SimpleNamespace

from opendbc.can import CANPacker, CANParser
from opendbc.car import Bus
from opendbc.car.hyundai.carstate import CarState, ioniq5_cluster_speed_limit
from opendbc.car.hyundai.values import CAR, HyundaiFlags


def test_ioniq5_instrument_sign_is_an_optional_camera_message():
  for candidate in (CAR.HYUNDAI_IONIQ_5, CAR.HYUNDAI_IONIQ_5_PE, CAR.KIA_EV6):
    cp = SimpleNamespace(carFingerprint=candidate, flags=HyundaiFlags.CANFD, extFlags=0, safetyConfigs=[None])
    parsers = CarState.__new__(CarState).get_can_parsers_canfd(cp)
    cam = parsers[Bus.cam]
    assert 0x1FA not in parsers[Bus.pt].addresses
    assert (0x1FA in cam.addresses) == (candidate == CAR.HYUNDAI_IONIQ_5)
    if candidate == CAR.HYUNDAI_IONIQ_5:
      assert cam.message_states[0x1FA].ignore_alive
      cam.update([1_000_000_000, []])
      assert cam.can_valid


def test_metric_cluster_primary_signs_require_agreement_and_fresh_camera_data():
  dbc = "hyundai_canfd_generated"
  cp = CANParser(dbc, [("CRUISE_BUTTONS_ALT", math.nan)], 0)
  cam = CANParser(dbc, [("CLUSTER_SPEED_LIMIT", math.nan)], 2)
  packer = CANPacker(dbc)
  stamp = 1_000_000_000

  def update(*, primary=80, other=80, bus=2, size=32, units=0):
    nonlocal stamp
    stamp += 100_000_000
    sign = packer.make_can_msg("CLUSTER_SPEED_LIMIT", bus, {
      "SPEED_LIMIT_1": primary, "SPEED_LIMIT_2": other,
      "SECONDARY_LIMIT_1": 60, "SECONDARY_LIMIT_2": 60, "SPEED_LIMIT_3": 85,
    })
    cam.update([stamp, [(sign[0], sign[1][:size], bus)]])
    if units is not None:
      unit_msg = packer.make_can_msg("CRUISE_BUTTONS_ALT", 0, {"DISTANCE_UNIT": units})
      cp.update([stamp, [unit_msg]])
    return ioniq5_cluster_speed_limit(cp, cam)

  assert update(units=None) == 0
  assert update(bus=0) == 80  # preceding fresh camera sample is still valid
  assert update() == 80
  assert update(primary=60, other=60) == 60
  assert update(primary=0, other=0) == 0
  assert update(primary=50, other=60) == 0
  assert update(primary=127, other=127) == 0
  assert update(size=8) == 0
  assert update(units=1) == 0
  assert update() == 80
  for _ in range(6):
    update(bus=0)
  assert ioniq5_cluster_speed_limit(cp, cam) == 0
  for _ in range(6):
    update(units=None)
  assert ioniq5_cluster_speed_limit(cp, cam) == 0
