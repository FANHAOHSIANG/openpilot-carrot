import pytest

from opendbc.car import structs
from opendbc.car.hyundai.low_speed_steer_reserve import LowSpeedSteerReserve, supports_reserve
from opendbc.car.hyundai.phase1 import supports_phase1


def state(**kw):
  return structs.CarState(canValid=True, vEgo=7, vEgoRaw=7, gearShifter='drive',
                          wheelSpeeds=dict(fl=7,fr=7,rl=7,rr=7), **kw)


def warm(helper, cs=None, **kw):
  args = dict(enabled=True, active=True, cs=cs or state(), base=270, demand=2.)
  args.update(kw)
  return [helper.update(model_frame=n // 5, **args) for n in range(100)]


@pytest.mark.parametrize('speed,ceiling', [(10, 409), (30, 409), (35, 339), (40, 270), (100, 270)])
@pytest.mark.parametrize('sign', [-1, 1])
def test_speed_ceiling_and_sustained_demand(speed, ceiling, sign):
  cs = state()
  cs.vEgo = cs.vEgoRaw = speed / 3.6
  trace = warm(LowSpeedSteerReserve(), cs, demand=sign * 2.)
  assert trace[:29] == [270] * 29
  assert trace[-1] == ceiling


@pytest.mark.parametrize('overrides', [dict(enabled=False), dict(active=False), dict(demand=.8),
                                    dict(demand=float('nan')), dict(base=409), dict(base=450)])
def test_no_unrequested_boost(overrides):
  assert set(warm(LowSpeedSteerReserve(), **overrides)) == {overrides.get('base', 270)}


@pytest.mark.parametrize('field,value', [('canValid', False), ('canTimeout', True), ('steerFaultTemporary', True),
                                       ('steerFaultPermanent', True), ('steeringPressed', True),
                                       ('standstill', True), ('steeringTorque', 251), ('gearShifter', 'reverse'),
                                       ('vEgoRaw', float('nan'))])
def test_health_loss_cancels_reserve_and_requires_requalification(field, value):
  helper, cs = LowSpeedSteerReserve(), state()
  assert warm(helper, cs)[-1] == 409
  previous = getattr(cs, field)
  setattr(cs, field, value)
  assert helper.update(enabled=True, active=True, cs=cs, base=270, model_frame=100, demand=1.2) == 270
  setattr(cs, field, previous)
  assert helper.update(enabled=True, active=True, cs=cs, base=270, model_frame=101, demand=1.2) == 270


def test_missing_stale_model_and_direction_reversal():
  helper, cs = LowSpeedSteerReserve(), state()
  assert warm(helper, cs)[-1] == 409
  args = dict(enabled=True, active=True, cs=cs, base=270, demand=1.2)
  assert helper.update(model_frame=None, **args) == 270
  assert all(helper.update(model_frame=19, **args) == 270 for _ in range(50))
  assert warm(helper, cs)[-1] == 409
  assert helper.update(model_frame=100, **dict(args, demand=-1.2)) == 270


def test_filtered_speed_cannot_hide_fast_raw_speed():
  cs = state()
  cs.vEgoRaw = 40 / 3.6
  assert set(warm(LowSpeedSteerReserve(), cs)) == {270}



@pytest.mark.parametrize("fingerprint,expected", [("HYUNDAI_IONIQ_5", True), ("KIA_EV6", True), ("UNKNOWN", False)])
def test_phase1_platform_scope(fingerprint, expected):
  from types import SimpleNamespace
  cp = SimpleNamespace(brand="hyundai", carFingerprint=fingerprint, dashcamOnly=False, notCar=False, steerControlType="torque")
  assert supports_phase1(cp) is expected
  cp.dashcamOnly = True
  assert not supports_phase1(cp)
