import ast
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('carrot_dec_under_test', ROOT / 'selfdrive/controls/lib/carrot_dec.py')
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
CarrotDEC = MODULE.CarrotDEC


def inputs(**updates):
  result = dict(enabled=True, experimental=True, original_mode='blended', valid=True,
                engaged=True, override=False, carrot_state='e2eCruise', soft_hold=False,
                speed=20.0, model_accel=0.0, model_stop=False,
                trajectory_speeds=[20.0] * 33, trajectory_times=[i / 3 for i in range(33)], dt=0.05)
  result.update(updates)
  return result


class TestCarrotDEC(unittest.TestCase):
  def test_setting_registration_and_menu(self):
    catalog = json.loads((ROOT / 'selfdrive/carrot_settings.json').read_text())
    entries = [p for p in catalog['params'] if p['name'] == 'CarrotDEC']
    self.assertEqual(len(entries), 1)
    self.assertEqual(entries[0]['default'], 0)
    self.assertIn('{"CarrotDEC", {PERSISTENT, BOOL, "0"}}', (ROOT / 'common/params_keys.h').read_text())
    def count(value):
      if isinstance(value, dict):
        return sum(count(v) for v in value.values())
      if isinstance(value, list):
        return sum(count(v) for v in value)
      return int(value == 'CarrotDEC')
    self.assertEqual(count(catalog['menu']), 1)

  def test_clear_cruise_uses_acc(self):
    d = CarrotDEC()
    for _ in range(1000):
      self.assertEqual(d.update(**inputs()).mode, 'acc')

  def test_brief_model_dips_do_not_switch(self):
    d = CarrotDEC()
    for _ in range(100):
      for _ in range(4):
        self.assertEqual(d.update(**inputs(model_accel=-0.6)).mode, 'acc')
      self.assertEqual(d.update(**inputs()).mode, 'acc')

  def test_persistent_slowdown_enters_after_confirmation(self):
    d = CarrotDEC()
    for _ in range(4):
      self.assertEqual(d.update(**inputs(model_accel=-0.6)).mode, 'acc')
    self.assertEqual(d.update(**inputs(model_accel=-0.6)).mode, 'blended')

  def test_release_requires_two_seconds(self):
    d = CarrotDEC()
    d.update(**inputs(model_stop=True))
    for _ in range(39):
      self.assertEqual(d.update(**inputs()).mode, 'blended')
    self.assertEqual(d.update(**inputs()).mode, 'acc')

  def test_new_slowdown_restarts_release_timer(self):
    d = CarrotDEC()
    d.update(**inputs(model_stop=True))
    for _ in range(30):
      d.update(**inputs())
    d.update(**inputs(model_accel=-0.6))
    for _ in range(39):
      self.assertEqual(d.update(**inputs()).mode, 'blended')
    self.assertEqual(d.update(**inputs()).mode, 'acc')

  def test_urgent_stop_and_prepare_are_immediate(self):
    for values in [dict(model_stop=True), dict(model_accel=-1.5), dict(carrot_state='e2ePrepare')]:
      with self.subTest(values=values):
        self.assertEqual(CarrotDEC().update(**inputs(**values)).mode, 'blended')

  def test_carrot_stop_obstacles_take_precedence(self):
    for state, hold in [('e2eStop', False), ('e2eStopped', False), ('lead', True)]:
      with self.subTest(state=state):
        r = CarrotDEC().update(**inputs(carrot_state=state, soft_hold=hold, model_stop=True))
        self.assertEqual((r.mode, r.reason), ('acc', 'carrot_stop'))

  def test_disabled_and_experimental_off_preserve_original_mode(self):
    for values in [dict(enabled=False), dict(experimental=False)]:
      for original in ['acc', 'blended']:
        r = CarrotDEC().update(**inputs(original_mode=original, model_stop=True, **values))
        self.assertEqual(r.mode, original)

  def test_invalid_and_driver_override_reset_history(self):
    for values in [dict(valid=False), dict(engaged=False), dict(override=True)]:
      d = CarrotDEC()
      d.update(**inputs(model_stop=True))
      r = d.update(**inputs(original_mode='acc', **values))
      self.assertEqual(r.mode, 'acc')
      self.assertEqual(d.update(**inputs(model_accel=-0.6)).mode, 'acc')

  def test_nonfinite_or_incomplete_inputs_retain_original(self):
    for values in [dict(speed=float('nan')), dict(model_accel=float('inf')),
                   dict(dt=0), dict(dt=0.3), dict(speed=-1), dict(trajectory_speeds=[]),
                   dict(trajectory_speeds=[float('nan')]*33), dict(trajectory_times=[0]*33)]:
      with self.subTest(values=values):
        r = CarrotDEC().update(**inputs(**values))
        self.assertEqual((r.mode, r.reason), ('blended', 'invalid'))

  def test_far_future_stop_does_not_force_blended(self):
    speeds = [20 if i < 10 else 0 for i in range(33)]
    self.assertEqual(CarrotDEC().update(**inputs(trajectory_speeds=speeds)).mode, 'acc')

  def test_near_future_speed_drop_confirms_blended(self):
    d = CarrotDEC()
    speeds = [20 if i < 2 else 15 for i in range(33)]
    for _ in range(5):
      r = d.update(**inputs(trajectory_speeds=speeds))
    self.assertEqual(r.mode, 'blended')

  def test_stationary_model_stop_and_clear_restart(self):
    d = CarrotDEC()
    self.assertEqual(d.update(**inputs(speed=0, model_stop=True)).mode, 'blended')
    for _ in range(40):
      r = d.update(**inputs(speed=0))
    self.assertEqual(r.mode, 'acc')

  def test_planner_selection_and_output_integration(self):
    # Execute actual planner blocks with stubbed services; no native MPC.
    source = (ROOT / 'selfdrive/controls/lib/longitudinal_planner.py').read_text()
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'LongitudinalPlanner')
    update = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'update')
    start = next(i for i,n in enumerate(update.body) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'dec_decision' for t in n.targets))
    end = next(i for i,n in enumerate(update.body[start:], start) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'prev_accel_constraint' for t in n.targets))
    output = next(n for n in update.body if isinstance(n, ast.If) and 'output_a_target = output_a_target_mpc' in ast.unparse(n))
    for enabled, accel, stop, expected in [(True,-.6,False,.2),(True,-1.5,False,-1.5),
                                           (True,0,True,0),(False,-.6,False,-.6)]:
      with self.subTest(enabled=enabled, accel=accel, stop=stop):
        obj = NS(dec=CarrotDEC(), dec_enabled=enabled, dec_last_log=None, dt=.05,
                 mpc=NS(mode='blended'), CP=NS(openpilotLongitudinalControl=True))
        carrot = NS(mode='blended', xState=NS(name='e2eCruise'), soft_hold_active=False)
        class Services(dict):
          def all_checks(self, **_): return True
        sm = Services(selfdriveState=NS(experimentalMode=True), carState=NS(gasPressed=False,brakePressed=False),
                      modelV2=NS(action=NS(desiredAcceleration=accel,shouldStop=stop),velocity=NS(x=[20]*33)))
        scope = dict(self=obj, sm=sm, carrot=carrot, reset_state=False, v_ego=20,
                     ModelConstants=NS(T_IDXS=[i/3 for i in range(33)]), cloudlog=NS(info=lambda _:None))
        exec(compile(ast.fix_missing_locations(ast.Module(body=update.body[start:end],type_ignores=[])), '<selection>', 'exec'), scope)
        self.assertEqual(obj.mpc.mode, carrot.mode)
        scope.update(output_a_target_mpc=.2,output_a_target_e2e=accel,
                     output_v_target_mpc=20,output_v_target_now_e2e=19,
                     output_should_stop_mpc=False,output_should_stop_e2e=stop)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[output],type_ignores=[])), '<output>', 'exec'), scope)
        self.assertEqual(scope['output_a_target'], expected)
        self.assertEqual(obj.output_should_stop,stop)


if __name__ == '__main__':
  unittest.main(verbosity=2)
