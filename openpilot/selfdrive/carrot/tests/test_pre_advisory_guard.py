import unittest
from openpilot.selfdrive.carrot.pre_advisory_guard import PreAdvisoryGuard, PreTransitionPreview, NO_LIMIT_KPH


class GuardTests(unittest.TestCase):
  def test_boundary(self):
    self.assertEqual(PreAdvisoryGuard().admit('a', 100, 80), 80)
    self.assertEqual(PreAdvisoryGuard().admit('a', 100, 120), 120)
  def test_gap(self):
    for target in (79.9, 120.1, 36, 60):
      g = PreAdvisoryGuard()
      self.assertEqual(g.admit('a', 100, target), NO_LIMIT_KPH)
      self.assertTrue(g.blocked)
  def test_no_rearm_on_speed_change_or_absence(self):
    g = PreAdvisoryGuard()
    self.assertEqual(g.admit('a', 100, 60), NO_LIMIT_KPH)
    self.assertEqual(g.admit('a', 65, 60), NO_LIMIT_KPH)
    self.assertEqual(g.admit('a', 65, 250), NO_LIMIT_KPH)
    self.assertEqual(g.admit('', 65, 60), NO_LIMIT_KPH)
    self.assertEqual(g.admit('a', 65, 60), NO_LIMIT_KPH)
    self.assertEqual(g.admit('b', 65, 60), 60)
  def test_invalid(self):
    for ego in (None, 0, -1, float('nan'), float('inf'), True):
      self.assertEqual(PreAdvisoryGuard().admit('a', ego, 60), NO_LIMIT_KPH)
  def test_other_cap_not_relaxed(self):
    self.assertEqual(min(30, PreAdvisoryGuard().admit('a', 100, 80)), 30)


class PreviewTests(unittest.TestCase):
  def test_linear_approach_and_recovery(self):
    p = PreTransitionPreview()
    key = ('a', 101, 'exit')
    self.assertEqual(p.step(key, 1_000_000_000, 100, 80, 100), 100)
    self.assertEqual(p.step(key, 2_000_000_000, 100, 80, 100), 97)
    self.assertEqual(p.step(key, 3_000_000_000, 97, 100, 100), 99)
  def test_lower_cap_immediate(self):
    p = PreTransitionPreview()
    p.step('a', 1_000_000_000, 100, 80, 100)
    self.assertEqual(p.step('a', 2_000_000_000, 97, 80, 40), 40)
  def test_withdrawal_clears_preview(self):
    p = PreTransitionPreview()
    p.step('a', 1_000_000_000, 100, 80, 100)
    self.assertIsNone(p.step('a', 2_000_000_000, 97, 250, 100))
    self.assertIsNone(p.value)
  def test_session_and_time_gap(self):
    p = PreTransitionPreview()
    p.step('a', 1_000_000_000, 100, 80, 100)
    self.assertEqual(p.step('b', 2_000_000_000, 95, 80, 100), 95)
    self.assertEqual(p.step('b', 4_000_000_000, 90, 80, 100), 90)


if __name__ == '__main__':
  unittest.main()
