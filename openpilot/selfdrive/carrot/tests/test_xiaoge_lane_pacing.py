"""Exercise the production camera loop without hardware/native cereal dependencies.

AST extraction only isolates imports; the run_road_camera body is executed unchanged.
Run directly with Python or under pytest.
"""
import ast
from pathlib import Path
import sys
import threading
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'xiaoge' / 'v_asm_server.py'


def camera_loop():
  tree = ast.parse(SOURCE.read_text())
  cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'VASMService')
  method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'run_road_camera')
  namespace = {}
  exec(compile(ast.Module(body=[method], type_ignores=[]), str(SOURCE), 'exec'), namespace)
  return namespace


class TestLanePacing(unittest.TestCase):
  def simulate(self, duration, interval=0.4, seconds=9, change_interval=None, fail_once=False):
    clock = SimpleNamespace(now=100.0)
    starts, snapshots, publications = [], [], []
    service = SimpleNamespace(
      running=True, lock=threading.Lock(), lane_camera_error='',
      snapshot_requests={'road': 0}, snapshot_responses={'road': 0},
      snapshot_condition=SimpleNamespace(notify_all=lambda: None),
      last_lane_inference_at=0.0, last_lane_inference_ms=0.0,
      lane_interval_seconds=interval, lane_threshold=0.6,
      lane_inference_count=0, _lane_fps_window_count=0,
      _lane_fps_window_start=clock.now, lane_inference_fps=0,
    )
    def advance(dt):
      clock.now += dt
    def refresh():
      if change_interval is not None and len(starts) >= 1:
        service.lane_interval_seconds = change_interval
    def infer(frame, width, height, conf_thresh):
      self.assertEqual((frame, width, height, conf_thresh), ('pixels', 8, 4, 0.6))
      starts.append(clock.now)
      advance(duration)
      if fail_once and len(starts) == 1:
        raise ValueError('inference failed')
      return {'lanes': ['unchanged']}
    def snapshot(*args):
      snapshots.append(clock.now)
      return b'jpeg'
    service._refresh_settings_from_params = refresh
    service._lane_jpeg_from_nv12 = snapshot
    service.lane_inference = SimpleNamespace(valid=True, infer=infer)
    service.publish_vision_result = lambda: publications.append(dict(service.lane_result))
    class Client:
      def __init__(self, *args):
        pass
      def is_connected(self):
        return True
      def connect(self, blocking):
        return True
      def recv(self, timeout_ms):
        advance(0.05)
        if clock.now >= 100.0 + seconds:
          service.running = False
          return None
        service.snapshot_requests['road'] += 1
        return SimpleNamespace(data=b'nv12', width=8, height=4, stride=8)
    ipc = ModuleType('msgq.visionipc')
    ipc.VisionIpcClient = Client
    ipc.VisionStreamType = SimpleNamespace(VISION_STREAM_ROAD=0)
    ns = camera_loop()
    ns.update(time=SimpleNamespace(monotonic=lambda: clock.now, monotonic_ns=lambda: int(clock.now*1e9),
                                  thread_time=lambda: clock.now, sleep=advance),
              nv12_y_plane=lambda *args: 'pixels', CAMERA_POLL_INTERVAL_SECONDS=0.005,
              cv2=SimpleNamespace(error=RuntimeError))
    with patch.dict(sys.modules, {'msgq.visionipc': ipc}):
      ns['run_road_camera'](service)
    return starts, snapshots, publications, service

  def test_overrun_leaves_equal_cooldown(self):
    starts, snapshots, publications, _ = self.simulate(1.3)
    self.assertGreaterEqual(len(starts), 3)
    self.assertTrue(all(b-a >= 2.6-1e-8 for a,b in zip(starts, starts[1:])), starts)
    self.assertGreater(len(snapshots), len(starts)*5)
    self.assertTrue(all(p['lanes'] == ['unchanged'] for p in publications))

  def test_fast_inference_keeps_configured_cadence(self):
    starts, _, _, _ = self.simulate(0.05, seconds=3)
    self.assertGreaterEqual(len(starts), 6)
    self.assertTrue(all(0.4-1e-8 <= b-a <= 0.45+1e-8 for a,b in zip(starts, starts[1:])), starts)

  def test_user_longer_interval_is_respected(self):
    starts, _, _, _ = self.simulate(0.1, interval=2)
    self.assertTrue(all(b-a >= 2-1e-8 for a,b in zip(starts, starts[1:])), starts)

  def test_runtime_interval_change(self):
    starts, _, _, _ = self.simulate(0.05, change_interval=1)
    self.assertTrue(all(b-a >= 1-1e-8 for a,b in zip(starts, starts[1:])), starts)

  def test_recovery_after_inference_error(self):
    starts, _, publications, service = self.simulate(0.1, fail_once=True)
    self.assertGreater(len(publications), 1)
    self.assertEqual(len(publications), len(starts)-1)
    self.assertEqual(service.lane_camera_error, '')


if __name__ == '__main__':
  unittest.main()
