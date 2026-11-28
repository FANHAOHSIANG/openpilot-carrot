import math
import unittest
from openpilot.selfdrive.carrot.low_speed_oscillation_shadow import Shadow, finite


class TestShadow(unittest.TestCase):
  def test_bypass_and_reset(self):
    s = Shadow()
    self.assertEqual(s.sample(1., .001, ""), (.001, "initial"))
    self.assertEqual(s.sample(1.05, -.001, "driver_or_fault"), (-.001, "driver_or_fault"))
    self.assertEqual(s.sample(1.1, .001, ""), (.001, "initial"))

  def test_20hz_candidate(self):
    s = Shadow()
    s.sample(1., .001, "")
    out, reason = s.sample(1.05, -.001, "")
    self.assertEqual(reason, "shadow_applied")
    self.assertAlmostEqual(out, .001 + (1 - math.exp(-.5)) * -.002)

  def test_gap_and_large_change(self):
    s = Shadow()
    s.sample(1., .001, "")
    self.assertEqual(s.sample(1.2, -.001, ""), (-.001, "gap"))
    self.assertEqual(s.sample(1.25, .01, ""), (.01, "large_change"))

  def test_invalid_and_nonfinite(self):
    s = Shadow()
    self.assertEqual(s.sample(1., math.nan, ""), (None, "nonfinite"))
    self.assertIsNone(finite(math.inf))
    self.assertEqual(s.sample(1.1, .001, ""), (.001, "initial"))

  def test_turn_bypass(self):
    s = Shadow()
    s.sample(1., .001, "")
    self.assertEqual(s.sample(1.05, .002, "turn_proxy"), (.002, "turn_proxy"))

  def test_no_control_publisher(self):
    import inspect
    from openpilot.selfdrive.carrot import low_speed_oscillation_shadow as mod
    source = inspect.getsource(mod)
    for forbidden in ("PubMaster(", "pub_sock(", "sendcan", "actuators.torque ="):
      self.assertNotIn(forbidden, source)


if __name__ == "__main__":
  unittest.main()
