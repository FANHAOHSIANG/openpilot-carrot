"""Separate angle authorization from Kick, using production C TX hooks."""
import pytest
from opendbc.car.hyundai.spas import frame
from opendbc.car.hyundai.values import HyundaiSafetyFlags as F
from opendbc.safety.tests.libsafety import libsafety_py
from opendbc.safety.tests.test_hyundai_canfd_steering_guard import Guard


@pytest.mark.parametrize('kick', [False, True])
@pytest.mark.parametrize('angle', [False, True])
@pytest.mark.parametrize('camera', [False, True])
@pytest.mark.parametrize('spas', [False, True])
def test_independent_authorizations_and_reinitialization(kick, angle, camera, spas):
  flags = int((F.CANFD_BLINKER_KICK if kick else 0) | (F.CANFD_ANGLE_CONTROL if angle else 0) |
              (F.CAMERA_SCC if camera else 0) | (F.CANFD_SPAS_BLINKERS if spas else 0))
  assert int(F.CANFD_ANGLE_CONTROL) == 512
  assert not (F.CANFD_ANGLE_CONTROL & F.CANFD_BLINKER_KICK)
  for param, expected_angle, expected_kick in [(flags, angle, kick and camera and not spas), (0, False, False)]:
    g = Guard(param)
    g.s.set_controls_allowed(True)
    packet = g.packer.make_can_msg_panda('LFA_ALT', 0,
      dict(LKAS_ANGLE_ACTIVE=2, LKAS_ANGLE_CMD=20, LKAS_ANGLE_MAX_TORQUE=25))
    assert bool(g.s.safety_tx_hook(packet)) is expected_angle
    packet = libsafety_py.make_CANPacket(0x16A, 0, frame(0x16A, 1, 'left', 0).dat)
    assert bool(g.s.safety_tx_hook(packet)) is expected_kick
    # Kick must never authorize excess torque, even when angle mode is off.
    g.seed(512)
    assert not g.tx(513)


@pytest.mark.parametrize('prior_angle', [False, True])
def test_classic_can_retains_its_512_alt_limits_after_canfd(prior_angle):
  from opendbc.car.structs import CarParams
  from opendbc.safety.tests.common import CANPackerPanda
  g = Guard(int(F.CANFD_ANGLE_CONTROL) if prior_angle else 0)
  assert g.s.set_safety_hooks(CarParams.SafetyModel.hyundai, int(F.ALT_LIMITS_2)) == 0
  g.s.init_tests()
  g.s.set_controls_allowed(True)
  packer = CANPackerPanda('hyundai_kia_generic')
  for torque, allowed in [(170, True), (171, False), (-170, True), (-171, False)]:
    g.seed(170 if torque > 0 else -170)
    packet = packer.make_can_msg_panda('LKAS11', 0, dict(CR_Lkas_StrToqReq=torque, CF_Lkas_ActToi=1))
    assert bool(g.s.safety_tx_hook(packet)) is allowed
