"""Source-level regression for the calibration odometry validity boundary.

Run: python3 -m unittest discover -s openpilot/selfdrive/locationd/tests -p 'test_calibration_odom_guard.py' -v
This test does not launch safety-critical processes.
"""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace


CALIBRATIOND = Path(__file__).resolve().parents[1] / "calibrationd.py"


def camera_condition():
  tree = ast.parse(CALIBRATIOND.read_text())
  main_fn = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == "main")
  loop = next(x for x in main_fn.body if isinstance(x, ast.While))
  guard = next(x for x in loop.body if isinstance(x, ast.If) and
               "sm.updated['cameraOdometry']" in ast.unparse(x.test))
  return guard.test


class CalibrationOdomGuardTest(unittest.TestCase):
  def test_only_updated_valid_odom_and_carstate_is_accepted(self):
    compiled = compile(ast.Expression(camera_condition()), str(CALIBRATIOND), "eval")
    for updated in (False, True):
      for odo_valid in (False, True):
        for car_valid in (False, True):
          sm = SimpleNamespace(
              updated={"cameraOdometry": updated},
              valid={"cameraOdometry": odo_valid, "carState": car_valid},
          )
          self.assertEqual(eval(compiled, {"sm": sm}),
                           updated and odo_valid and car_valid)

  def test_original_publish_validity_gate_still_present(self):
    tree = ast.parse(CALIBRATIOND.read_text())
    main_fn = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == "main")
    calls = [x for x in ast.walk(main_fn) if isinstance(x, ast.Call)]
    self.assertTrue(any(ast.unparse(c) == "calibrator.send_data(pm, sm.all_checks())"
                        for c in calls), "Must not bypass calibration message validity")


if __name__ == "__main__":
  unittest.main()
