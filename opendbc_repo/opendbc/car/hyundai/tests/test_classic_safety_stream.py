from collections import defaultdict
from types import SimpleNamespace as NS

import pytest
from opendbc.car import Bus, structs, get_safety_config
from opendbc.car.hyundai import carcontroller
from opendbc.car.hyundai.values import CAR, HyundaiSafetyFlags as F
from opendbc.safety.tests.libsafety import libsafety_py


@pytest.mark.parametrize('model,flags', [(structs.CarParams.SafetyModel.hyundai, 0),
  (structs.CarParams.SafetyModel.hyundaiLegacy, 0), (structs.CarParams.SafetyModel.hyundai, int(F.ALT_LIMITS)),
  (structs.CarParams.SafetyModel.hyundai, int(F.ALT_LIMITS_2)), (structs.CarParams.SafetyModel.hyundai, int(F.CAMERA_SCC))])
@pytest.mark.parametrize('custom', [False, True])
@pytest.mark.parametrize('period', [10_000, 9_091])
def test_classic_controller_stream(monkeypatch, model, flags, custom, period):
  settings = {'MaxAngleFrames': 30 if custom else 89}
  if custom:
    settings.update(CustomSteerMax=1000, CustomSteerDeltaUp=10, CustomSteerDeltaDown=1,
                    CustomSteerDeltaUpLC=10, CustomSteerDeltaDownLC=1)
  params = NS(get_int=lambda k: settings.get(k, 0), get_bool=lambda k: False)
  monkeypatch.setattr(carcontroller, 'Params', lambda: params)
  monkeypatch.setattr(carcontroller.CarController, 'create_button_messages', lambda *a, **kw: [])
  cp = structs.CarParams(carFingerprint=CAR.HYUNDAI_SONATA, wheelbase=2.84, steerRatio=14.26)
  cp.safetyConfigs = [get_safety_config(model, flags)]
  cc = structs.CarControl(enabled=True, latActive=True)
  cs = NS(out=structs.CarState(canValid=True, vEgo=15, vEgoRaw=15), modelV2=None, is_metric=True, lkas11=None, mdps12=None)
  controller = carcontroller.CarController({Bus.pt: 'hyundai_kia_generic'}, cp)
  safety = libsafety_py.libsafety
  assert safety.set_safety_hooks(model, flags) == 0
  safety.init_tests()
  safety.set_controls_allowed(True)
  sent = []
  for i in range(1500):
    cs.lkas11 = defaultdict(int) if i >= 120 else None
    cc.actuators.torque = 1 if i < 700 else -1
    cc.hudControl.modelDesire = 3 if i % 200 < 100 else 0
    cs.out.steeringTorque = -1000 if 400 <= i < 500 else 1000 if 1100 <= i < 1200 else 0
    cs.out.steeringAngleDeg = 90 if 150 <= i < 400 or 800 <= i < 1100 else 0
    cc.latActive = not 600 <= i < 650
    safety.set_torque_driver(int(cs.out.steeringTorque), int(cs.out.steeringTorque))
    safety.set_timer(i * period)
    output, messages = controller.update(cc.as_reader(), cs, i * period * 1000)
    for addr, dat, bus in messages:
      if addr == 0x340:
        assert safety.safety_tx_hook(libsafety_py.make_CANPacket(addr, bus, dat)), (i, output.torqueOutputCan)
        sent.append(output.torqueOutputCan)
  assert len(sent) > 1300
  assert max(sent) >= 100 and min(sent) <= -100
