import importlib
import math
import sys
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from openpilot.cereal import log

# This is the camera input/planner message contract test. In headless x86 CI
# the acados solver has no pre-generated Cython extension; isolate only that
# numerical solver while retaining the actual upstream LongitudinalPlanner,
# camera lead processing, validity checks, speed cap, and publish path.
# If native solver is present, no test substitute is installed.
_NATIVE = "openpilot.selfdrive.controls.lib.upstream_mpc.c_generated_code"
_SOLVER = f"{_NATIVE}.acados_ocp_solver_pyx"
try:
  importlib.import_module(_SOLVER)
  HAS_NATIVE_SOLVER = True
except ModuleNotFoundError as exc:
  if exc.name not in (_NATIVE, _SOLVER):
    raise
  HAS_NATIVE_SOLVER = False
  package = ModuleType(_NATIVE)
  package.__path__ = []
  extension = ModuleType(_SOLVER)
  class MissingNativeSolver:
    def __init__(self, *args, **kwargs):
      raise RuntimeError("native acados extension unavailable in headless CI")
  extension.AcadosOcpSolverCython = MissingNativeSolver
  sys.modules[_NATIVE] = package
  sys.modules[_SOLVER] = extension

from openpilot.selfdrive.controls.lib import upstream_planner
from openpilot.selfdrive.controls.lib.upstream_planner import LongitudinalPlanner
from openpilot.selfdrive.controls.lib.upstream_mpc.long_mpc import T_IDXS


class OfflineMpc:
  """Bounded deterministic stub for messaging contract tests, NOT MPC safety."""
  def __init__(self, dt):
    self.dt = dt
    self.source = log.LongitudinalPlan.LongitudinalPlanSource.cruise
    self.v_solution = np.full(len(T_IDXS), 12.)
    self.a_solution = np.full(len(T_IDXS), -.4)
    self.j_solution = np.zeros(len(T_IDXS)-1)
    self.crash_cnt = 0
    self.solve_time = 0.

  def set_weights(self, *args, **kwargs):
    return None

  def set_cur_state(self, *args, **kwargs):
    return None

  def update(self, leads, **kwargs):
    source = log.LongitudinalPlan.LongitudinalPlanSource
    self.source = source.lead0 if leads.leadOne.status else source.cruise


@pytest.fixture(autouse=True)
def offline_solver_only_if_native_missing(monkeypatch):
  if not HAS_NATIVE_SOLVER:
    monkeypatch.setattr(upstream_planner, "LongitudinalMpc", OfflineMpc)




@pytest.mark.parametrize("brand", ["toyota", "subaru", "hyundai", "honda"])
@pytest.mark.parametrize("owns_long", [True, False])
def test_vision_planning_without_a_radar_publisher(brand, owns_long):
  cp = SimpleNamespace(brand=brand, openpilotLongitudinalControl=owns_long, longitudinalActuatorDelay=.2)
  planner = LongitudinalPlanner(cp, vision_only=True)
  model = log.ModelDataV2.new_message()
  model.velocity.x = [12.]
  model.action.desiredAcceleration = -.7
  model.action.shouldStop = True
  leads = model.init("leadsV3", 2)
  for lead in leads:
    lead.x, lead.y, lead.v, lead.a = [25.], [1.], [10.], [0.]
    lead.prob = .95
  leads[1].x = [float("nan")]

  class Inputs(dict):
    logMonoTime = {"modelV2": 1}
    def all_checks(self, names):
      return all(name in self for name in names)

  sm = Inputs(modelV2=model, carState=SimpleNamespace(vEgo=12., vCruise=110., aEgo=0., standstill=False),
              controlsState=SimpleNamespace(forceDecel=False, longControlState="pid"),
              selfdriveState=SimpleNamespace(personality=SimpleNamespace(raw=1), enabled=True),
              liveParameters=SimpleNamespace(roll=0.))
  sent = {}
  planner.update(sm)
  planner.publish(sm, SimpleNamespace(send=sent.__setitem__))
  msg = sent["longitudinalPlan"]
  plan = msg.longitudinalPlan
  assert msg.valid and plan.plannerProfile == "visionE2e"
  assert plan.shouldStop and math.isfinite(plan.aTarget) and plan.aTarget < 0
  assert plan.cruiseTarget == 110
  assert plan.cameraLeadState.leadOne.vRel == -2.
  assert plan.cameraLeadState.leadOne.status and not plan.cameraLeadState.leadOne.radar
  assert not plan.cameraLeadState.leadTwo.status
  assert (plan.speedConstraint == "stockLong") == (not owns_long)
  model.init("leadsV3", 0)
  planner.update(sm)
  assert not planner.leads.leadOne.status
  model.action.desiredAcceleration = math.nan
  planner.update(sm)
  planner.publish(sm, SimpleNamespace(send=sent.__setitem__))
  assert not sent["longitudinalPlan"].valid
