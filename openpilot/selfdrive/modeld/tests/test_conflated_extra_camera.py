"""Non-driving regression tests for synchronized camera pairs.

These tests mock VisionIPC buffers. A production camera driver and model
deadline test are still required before enabling the experiment on a car.
"""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace

from openpilot.selfdrive.modeld.camera_sync import MAX_CAMERA_SKEW_NS, receive_camera_pair


class FakeCamera:
  def __init__(self, frames):
    self.frames = iter(frames)
    self.frame_id = 0
    self.timestamp_sof = 0
    self.timestamp_eof = 0

  def recv(self):
    try:
      frame_id, sof = next(self.frames)
    except StopIteration:
      return None
    self.frame_id = frame_id
    self.timestamp_sof = sof
    self.timestamp_eof = sof + 20_000_000
    return object()


class ConflatedCameraExperimentTest(unittest.TestCase):
  def test_current_pair_accepted(self):
    main = FakeCamera([(22, 1_000_000_000)])
    extra = FakeCamera([(22, 1_001_000_000)])
    self.assertIsNotNone(receive_camera_pair(main, extra))

  def test_stale_extra_is_drained_to_matching_sof(self):
    main = FakeCamera([(22, 1_000_000_000)])
    extra = FakeCamera([(20, 900_000_000), (21, 950_000_000),
                        (22, 1_000_500_000)])
    frames = receive_camera_pair(main, extra)
    self.assertIsNotNone(frames)
    self.assertEqual(frames[3].frame_id, 22)

  def test_stale_pair_is_never_accepted(self):
    main = FakeCamera([(22, 1_000_000_000)])
    extra = FakeCamera([(20, 900_000_000)])
    self.assertIsNone(receive_camera_pair(main, extra))

  def test_skew_threshold_unchanged(self):
    self.assertEqual(MAX_CAMERA_SKEW_NS, 20_000_000)

  def test_extra_client_conflation_only(self):
    source = (Path(__file__).resolve().parents[1] / "modeld.py").read_text()
    tree = ast.parse(source)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == "VisionIpcClient"]
    self.assertTrue(any(len(c.args) == 3 and isinstance(c.args[2], ast.Constant)
                        and c.args[2].value is True
                        and isinstance(c.args[1], ast.Attribute)
                        and c.args[1].attr == "VISION_STREAM_WIDE_ROAD"
                        for c in calls))


if __name__ == "__main__":
  unittest.main()
