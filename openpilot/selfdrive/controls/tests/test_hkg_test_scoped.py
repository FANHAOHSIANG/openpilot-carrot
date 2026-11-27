"""Offline checks for the Test-only, no-extra-torque HKG integration."""
import ast
import math
import time
from pathlib import Path
from types import SimpleNamespace as NS

import numpy as np
import pytest

from opendbc.car.hyundai.phase1 import phase1_enabled
from openpilot.selfdrive.controls.lib.hkg_phase1 import CurveSpeedEnvelope, low_speed_response_tau, smooth_curvature
from openpilot.selfdrive.modeld.constants import ModelConstants

ROOT = Path(__file__).resolve().parents[4]

@pytest.mark.parametrize("enabled", [False, True])
def test_platform_and_switch(enabled):
  cp = NS(brand="hyundai", carFingerprint="HYUNDAI_IONIQ_5", dashcamOnly=False, notCar=False, steerControlType="torque")
  params = NS(get_bool=lambda key: enabled)
  assert phase1_enabled(cp, params) == enabled
  cp.dashcamOnly = True
  assert not phase1_enabled(cp, params)

@pytest.mark.parametrize("target,prev", [(.01,.005),(-.01,-.005)])
def test_bounded_turn_in(target, prev):
  tau = low_speed_response_tau(target, prev, 5., .1)
  assert tau == pytest.approx(.06)
  val = smooth_curvature(target, prev, 5., .01, tau)
  assert min(target, prev) <= val <= max(target, prev)
  assert low_speed_response_tau(-target, prev, 5., .1) == .1

def test_highway_filter_attenuates_small_corrections():
  previous = 0.
  baseline, shaped = [], []
  old = 0.
  for i in range(1200):
    target = .001 + .0001 * math.sin(i * .01 * 2 * math.pi * 3)
    old += (target-old) * (1-math.exp(-.01/.1))
    previous = smooth_curvature(target, previous, 30., .01, .1)
    baseline.append(old)
    shaped.append(previous)
  assert np.std(shaped[500:]) < np.std(baseline[500:])
  assert np.mean(shaped[500:]) == pytest.approx(.001, abs=2e-6)

def production_method(path, cls, name, ns):
  tree = ast.parse((ROOT / path).read_text())
  node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
  fn = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == name)
  exec(compile(ast.Module(body=[fn], type_ignores=[]), path, "exec"), ns)
  return ns[name]

@pytest.mark.parametrize("admitted", [False, True])
def test_actual_planner_requires_fresh_engaged_acc(admitted):
  class SM(dict):
    recv_time = {"modelV2": time.monotonic()}
    def all_checks(self, _): return True
  t = np.array(ModelConstants.T_IDXS)
  m = NS(frameId=1, position=NS(x=t*25,y=t*0,z=t*0),
         velocity=NS(x=np.full_like(t,25.)), orientationRate=NS(z=np.full_like(t,.3)))
  cs = NS(vEgo=25., canValid=True, canTimeout=False, steerFaultTemporary=False,
          steerFaultPermanent=False, gasPressed=False, brakePressed=False, steeringPressed=False,
          gearShifter="drive", standstill=False)
  sm = SM(carState=cs, modelV2=m, carControl=NS(latActive=True,longActive=admitted), selfdriveState=NS(enabled=True))
  p = NS(CP=NS(openpilotLongitudinalControl=True), mpc=NS(mode="acc"), hkg_curve=CurveSpeedEnvelope(),
         hkg_phase1_enabled=True, dt=.05)
  fn = production_method("openpilot/selfdrive/controls/lib/longitudinal_planner.py", "LongitudinalPlanner",
                         "update_hkg_curve_speed", {"time":time})
  for f in range(1,5):
    m.frameId=f
    result=fn(p,sm,30.,False)
  assert (result < 30.) == admitted
  sm.recv_time={"modelV2":time.monotonic()-1}
  assert fn(p,sm,30.,False)==30.
  assert p.hkg_curve_ceiling is None

def test_scoped_switches_remain_default_off_and_reserve_is_not_implicitly_enabled():
  import json
  data=json.loads((ROOT/"openpilot/selfdrive/carrot_settings.json").read_text())
  by={p["name"]:p for p in data["params"]}
  for name in ("HkgPhase1Assist","LowSpeedSteerObserveOnly"):
    assert by[name]["default"]==0 and by[name]["control"]=="toggle"
  assert "LowSpeedSteerReserve" not in by
  source=(ROOT/"opendbc_repo/opendbc/car/hyundai/carcontroller.py").read_text()
  # The separate staging parameter is not exposed in the settings UI.
  keys=(ROOT/"openpilot/common/params_keys.h").read_text()
  assert '{"LowSpeedSteerReserve", {PERSISTENT, BOOL, "0"}}' in keys
  tree=ast.parse(source)
  assignments=[n for n in ast.walk(tree) if isinstance(n, ast.Assign)
               and any(ast.unparse(t)=="self.reserve_enabled" for t in n.targets)]
  assert {ast.unparse(n.value) for n in assignments} == {
    "False", "self.reserve_supported and params.get_bool('LowSpeedSteerReserve')"}
  # A runtime regression in test_low_speed_steer_reserve separately verifies
  # that HkgPhase1Assist alone never activates additional torque.

