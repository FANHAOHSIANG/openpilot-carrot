import math
import unittest
from low_speed_oscillation_candidate import Experiment, OfflineCandidate


class TestCandidate(unittest.TestCase):
  def setUp(self):
    # Synthetic fixture units only; not vehicle calibration.
    self.c = OfflineCandidate(Experiment(5, .02, .004, .1, .05))

  def step(self, t, target, **kwargs):
    args = dict(enabled=True, valid=True, driver_override=False, turning=False, speed=2)
    args.update(kwargs)
    return self.c.step(t=t, target=target, **args)

  def test_disabled(self):
    for i in range(20):
      target = (-1)**i * .001
      self.assertEqual(self.step(i*.01, target, enabled=False), (target, False))

  def test_noise(self):
    raw = [(-1)**i*.001 for i in range(100)]
    out = [self.step(i*.01, v)[0] for i, v in enumerate(raw)]
    travel = lambda a: sum(abs(x-y) for x,y in zip(a,a[1:]))
    self.assertLess(travel(out), travel(raw)*.2)

  def test_turn_bypass(self):
    self.step(0, 0)
    self.assertEqual(self.step(.01, .015, turning=True), (.015, False))
    self.assertEqual(self.step(.02, .001), (.001, False))

  def test_large_step(self):
    self.step(0, 0)
    self.assertEqual(self.step(.01, .01), (.01, False))

  def test_exit(self):
    for flag in ({'valid':False}, {'driver_override':True}, {'speed':6}, {'speed':0}, {'enabled':False}):
      self.step(0, 0)
      self.assertEqual(self.step(.01, .001, **flag), (.001, False))
      self.assertEqual(self.step(.02, .001), (.001, False))
      self.c.reset()

  def test_gap(self):
    self.step(0, 0)
    self.assertEqual(self.step(.2, .001), (.001, False))
    self.assertEqual(self.step(.1, -.001), (-.001, False))

  def test_nonfinite(self):
    self.step(0, 0)
    with self.assertRaises(ValueError):
      self.step(.01, math.nan)
    self.assertEqual(self.step(.02, .001), (.001, False))

  def test_constant(self):
    for i in range(20):
      self.assertEqual(self.step(i*.01, .001)[0], .001)

  def test_invalid_configuration(self):
    with self.assertRaises(ValueError):
      Experiment(5, .02, .004, 0, .05)


if __name__ == '__main__':
  unittest.main()
