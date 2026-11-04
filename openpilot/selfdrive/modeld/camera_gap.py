"""Bounded per-gap evidence; never changes camera selection or pose validity."""
import time

from openpilot.selfdrive.modeld.camera_sync import receive_camera_pair


class CameraGapTrace:
  def __init__(self, emit):
    self.emit = emit
    self.received = []
    self.previous = None
    self.next_emit = 0.
    self.next_pair_emit = 0.

  def receive(self, main, extra):
    self.received = []
    frames = receive_camera_pair(main, extra, trace=self.received)
    if frames is None:
      now = time.monotonic()
      if now >= self.next_pair_emit:
        self.next_pair_emit = now + 1.
        try:
          # Diagnostics only. The camera pairing and frame validity gates
          # remain unchanged; never re-use a previous camera frame.
          self.emit('modelCameraPairUnavailable', mono_time=now,
                    received=list(self.received), previous=self.previous)
        except Exception:
          pass
    return frames

  def record(self, frame_id, dropped, backend, **timings):
    current = {'frame_id': frame_id, 'backend': backend, 'received': self.received,
               'timings_ms': {k: round(v, 3) for k, v in timings.items()}}
    now = time.monotonic()
    if dropped and now >= self.next_emit:
      self.next_emit = now + 1.
      try:
        self.emit('modelCameraGap', mono_time=now, dropped=dropped, previous=self.previous, current=current)
      except Exception:
        pass
    self.previous = current
