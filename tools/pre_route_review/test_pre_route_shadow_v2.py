import unittest
from dataclasses import replace
from pre_route_shadow_v2 import RouteAudit, RouteContext, Event

C = RouteContext('session', 'route1', 1, True)
E = Event('session', 'route1', 1, 'ramp1', 1, 'exit', 80, 100, 200, 20, 100, True)

class AuditTests(unittest.TestCase):
  def test_lifecycle(self):
    a = RouteAudit()
    self.assertEqual(a.observe(C, E), 'before_entry')
    self.assertEqual(a.observe(C, replace(E, sequence=2, progress=120, distance=-20)), 'within_ramp')
    self.assertEqual(a.observe(C, replace(E, sequence=3, progress=200, distance=-100)), 'completed')
    self.assertEqual(a.observe(C, replace(E, sequence=4)), 'retired')
  def test_replan_old_packet(self):
    a = RouteAudit()
    a.observe(C, E)
    new = replace(C, route='route2', revision=2)
    self.assertEqual(a.observe(new, replace(E, route='route2', revision=2)), 'before_entry')
    self.assertEqual(a.observe(new, E), 'not_current_route')
    self.assertEqual(a.observe(C, E), 'old_context')
  def test_unrelated_exit(self):
    self.assertEqual(RouteAudit().observe(C, replace(E, route='unrelated')), 'not_current_route')
  def test_completion_contradiction(self):
    self.assertEqual(RouteAudit().observe(C, replace(E, completed=True)), 'inconsistent_completion')
    self.assertEqual(RouteAudit().observe(C, replace(E, completed=True, distance=1000)), 'inconsistent_geometry')
  def test_duplicate_and_progress(self):
    a = RouteAudit()
    a.observe(C, E)
    self.assertEqual(a.observe(C, E), 'old_event')
    self.assertEqual(a.observe(C, replace(E, sequence=2, progress=70, distance=30)), 'old_event')
  def test_guidance_off(self):
    self.assertEqual(RouteAudit().observe(replace(C, active=False), E), 'no_guidance')
  def test_stale_and_gps(self):
    for e in (replace(E, age_ms=2000), replace(E, matched=False)):
      self.assertEqual(RouteAudit().observe(C, e), 'unverified_position')
  def test_far_is_not_permission(self):
    self.assertEqual(RouteAudit().observe(C, replace(E, entry=100000, end=100100, distance=99920)), 'before_entry')
  def test_bad_geometry(self):
    self.assertEqual(RouteAudit().observe(C, replace(E, progress=float('nan'))), 'invalid_geometry')
  def test_new_session(self):
    a = RouteAudit()
    a.observe(C, E)
    self.assertEqual(a.observe(replace(C, session='next'), E), 'not_current_route')
  def test_non_ramp(self):
    self.assertEqual(RouteAudit().observe(C, replace(E, kind='straight')), 'not_ramp')

if __name__ == '__main__':
  unittest.main()
