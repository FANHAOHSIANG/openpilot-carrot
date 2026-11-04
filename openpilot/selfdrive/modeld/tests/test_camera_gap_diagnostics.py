"""Isolated camera-pair diagnostics tests; no vehicle or GPU required."""
import importlib.util
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / 'camera_gap.py'

# Mock only the imported camera pairing helper. The test does not start modeld.
for name in ('openpilot', 'openpilot.selfdrive', 'openpilot.selfdrive.modeld'):
  sys.modules.setdefault(name, types.ModuleType(name))
camera_sync = types.ModuleType('openpilot.selfdrive.modeld.camera_sync')
camera_sync.receive_camera_pair = lambda *args, **kwargs: None
sys.modules['openpilot.selfdrive.modeld.camera_sync'] = camera_sync
spec = importlib.util.spec_from_file_location('camera_gap_under_test', MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CameraGapDiagnosticsTest(unittest.TestCase):
  def test_unavailable_pairs_are_rate_limited_and_never_replaced(self):
    events = []
    trace = module.CameraGapTrace(lambda *args, **kwargs: events.append((args, kwargs)))
    with patch.object(module, 'receive_camera_pair', return_value=None) as receive, \
         patch.object(module.time, 'monotonic', side_effect=[10., 10.3, 11.1]):
      assert trace.receive(None, None) is None
      assert trace.receive(None, None) is None
      assert trace.receive(None, None) is None
    self.assertEqual(receive.call_count, 3)
    self.assertEqual([e[0][0] for e in events], ['modelCameraPairUnavailable'] * 2)

  def test_successful_pair_is_returned_unchanged(self):
    events = []
    trace = module.CameraGapTrace(lambda *args, **kwargs: events.append((args, kwargs)))
    pair = (object(), object(), object(), object())
    with patch.object(module, 'receive_camera_pair', return_value=pair):
      self.assertIs(trace.receive(None, None), pair)
    self.assertEqual(events, [])

  def test_diagnostics_failure_does_not_change_camera_behavior(self):
    def broken_emit(*args, **kwargs):
      raise RuntimeError('logging unavailable')
    trace = module.CameraGapTrace(broken_emit)
    with patch.object(module, 'receive_camera_pair', return_value=None), \
         patch.object(module.time, 'monotonic', return_value=10.):
      self.assertIsNone(trace.receive(None, None))

  def test_existing_dropped_frame_reporting_unchanged(self):
    events = []
    trace = module.CameraGapTrace(lambda *args, **kwargs: events.append((args, kwargs)))
    with patch.object(module.time, 'monotonic', return_value=20.):
      trace.record(24, 2, 'Jetlink', loop=61.2)
      trace.record(25, 0, 'Jetlink', loop=49.5)
    self.assertEqual([e[0][0] for e in events], ['modelCameraGap'])
    self.assertEqual(events[0][1]['dropped'], 2)


if __name__ == '__main__':
  unittest.main()
