"""Run the production publish method with mocked transport (no vehicle/native dependencies)."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import MagicMock

SOURCE = Path(__file__).resolve().parents[1] / 'controlsd.py'
if not SOURCE.exists():
  SOURCE = Path(__file__).with_name('controlsd.py')

class TestPublishPlanAge(unittest.TestCase):
  def publish(self, plan_age=0, radar_age=0, valid=True):
    tree = ast.parse(SOURCE.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Controls')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'publish')
    signal = MagicMock(side_effect=lambda *a, inputs_ready: inputs_ready)
    messaging = MagicMock()
    ns = dict(CV=NS(KPH_TO_MS=1/3.6), DT_CTRL=0.01, get_carrot_man=lambda sm: None,
              signal_stop_object_requested=signal, driver_monitoring_hud_alert=lambda sm: 0,
              messaging=messaging, State=NS(softDisabling='softDisabling'),
              log=NS(DriverMonitoringState=NS(AlertLevel=NS(three=3))),
              car=NS(CarParams=NS(SteerControlType=NS(angle='angle'))))
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(SOURCE), 'exec'), ns)
    class SM(dict):
      pass
    sm = SM({k:MagicMock() for k in ['carState','longitudinalPlan','carrotMan','selfdriveState',
                                    'radarState','modelV2','driverMonitoringState']})
    sm.frame = 100
    sm.recv_frame = {'longitudinalPlan':100-plan_age, 'radarState':100-radar_age}
    sm.logMonoTime = {'longitudinalPlan':1, 'modelV2':1}
    sm.valid = {'driverAssistance':False}
    sm.all_checks = lambda services: valid
    sm['carState'].vCruiseCluster = 80
    sm['carState'].vCluRatio = 1
    sm['longitudinalPlan'].speeds = []
    sm['selfdriveState'].personality.raw = 0
    sm['selfdriveState'].active = False
    sm['modelV2'].meta.desireState = []
    sm['driverMonitoringState'].dm2Disabled = True
    cp = MagicMock()
    cp.pcmCruise = False
    cp.steerControlType = 'torque'
    cp.lateralTuning.which.return_value = 'torque'
    selfobj = MagicMock()
    selfobj.sm = sm
    selfobj.CP = cp
    selfobj.calibrated_pose = None
    selfobj.is_vw_meb = False
    selfobj.LoC.pid.p = selfobj.LoC.pid.i = selfobj.LoC.pid.f = 0
    cc = MagicMock()
    ns['publish'](selfobj, cc, MagicMock())
    self.assertEqual([c.args[0] for c in selfobj.pm.send.call_args_list], ['controlsState','carControl'])
    return signal.call_args.kwargs['inputs_ready']

  def test_fresh_inputs_publish_both_messages(self):
    self.assertTrue(self.publish())
  def test_freshness_boundary(self):
    self.assertTrue(self.publish(plan_age=20, radar_age=20))
  def test_stale_plan_rejected(self):
    self.assertFalse(self.publish(plan_age=21))
  def test_future_plan_rejected(self):
    self.assertFalse(self.publish(plan_age=-1))
  def test_stale_radar_rejected(self):
    self.assertFalse(self.publish(radar_age=21))
  def test_future_radar_rejected(self):
    self.assertFalse(self.publish(radar_age=-1))
  def test_invalid_inputs_rejected(self):
    self.assertFalse(self.publish(valid=False))

if __name__ == '__main__':
  unittest.main()
