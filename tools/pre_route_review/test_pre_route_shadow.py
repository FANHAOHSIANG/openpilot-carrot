import unittest
from dataclasses import replace
from pre_route_shadow import Observation, PreRouteShadow

BASE = Observation('session1', 'route1', 'route1', 'ramp1', 'exit', True, False, True, False, 80, 100, 200, 20, 100)

class ShadowTests(unittest.TestCase):
  def test_lifecycle(self):
    s = PreRouteShadow()
    self.assertEqual(s.observe(BASE), 'approach')
    self.assertEqual(s.observe(replace(BASE, progress_m=120, distance_to_entry_m=-20)), 'on_ramp')
    self.assertEqual(s.observe(replace(BASE, progress_m=200, distance_to_entry_m=-100)), 'completed')
    self.assertEqual(s.observe(BASE), 'retired')
    self.assertEqual(s.observe(replace(BASE, event_id='ramp2', progress_m=220, entry_m=300, end_m=400, distance_to_entry_m=80)), 'approach')
  def test_unrelated_ramp(self):
    self.assertEqual(PreRouteShadow().observe(replace(BASE, event_route='other')), 'not_selected_route')
  def test_no_guidance_or_off_route(self):
    for o in (replace(BASE, guidance_active=False), replace(BASE, off_route=True)):
      self.assertEqual(PreRouteShadow().observe(o), 'no_guidance')
  def test_invalid_data(self):
    for o, reason in ((replace(BASE, age_ms=2000),'unverified_position'), (replace(BASE, position_matched=False),'unverified_position'), (replace(BASE, event_id=''),'missing_identity'), (replace(BASE, kind='straight'),'not_ramp'), (replace(BASE, progress_m=float('nan')),'invalid_geometry'), (replace(BASE, end_m=50),'invalid_geometry'), (replace(BASE, distance_to_entry_m=100),'inconsistent_distance')):
      self.assertEqual(PreRouteShadow().observe(o), reason)
  def test_completion_flag(self):
    s = PreRouteShadow()
    self.assertEqual(s.observe(replace(BASE, completed=True)), 'completed')
    self.assertEqual(s.observe(BASE), 'retired')
  def test_progress_regression(self):
    s = PreRouteShadow()
    self.assertEqual(s.observe(replace(BASE, progress_m=150, distance_to_entry_m=-50)), 'on_ramp')
    self.assertEqual(s.observe(BASE), 'regressed_progress')
  def test_session_change(self):
    s = PreRouteShadow()
    s.observe(BASE)
    self.assertEqual(s.observe(replace(BASE, session='session2')), 'session_changed')

if __name__ == '__main__':
  unittest.main()
