import json
import resource
import signal
import sys
import time
from types import ModuleType
from types import SimpleNamespace

import numpy as np
import pytest

from openpilot.tools.clearance_shadow.live_observer import (ARM_DURATION_NS, arm_worker, healthy, next_delay,
                                                           requested, status_snapshot, write_status)
from openpilot.tools.clearance_shadow.onnx_observer import decode_output, letterbox_rgb
import openpilot.tools.clearance_shadow.live_observer as live


def test_arm_is_opt_in_time_limited_and_rejects_bad_files(tmp_path):
  now = 2_000_000_000_000
  path = tmp_path / 'armed.json'
  assert not requested(tmp_path, now)
  path.write_text(json.dumps({'version': 1, 'expires_monotonic_ns': now + 3_000_000_000}))
  assert requested(tmp_path, now)
  assert not requested(tmp_path, now + 3_000_000_000)
  path.write_text(json.dumps({'version': 1, 'expires_monotonic_ns': now + ARM_DURATION_NS + 1}))
  assert not requested(tmp_path, now)
  path.write_text('{')
  assert not requested(tmp_path, now)
  path.unlink()
  target = tmp_path / 'target'
  target.write_text(json.dumps({'version': 1, 'expires_monotonic_ns': now + 1}))
  path.symlink_to(target)
  assert not requested(tmp_path, now)


def test_rate_limit_charges_cpu_time_and_never_catches_up():
  assert next_delay(.2, .05) == pytest.approx(.8)
  assert next_delay(2, .4) == pytest.approx(3.6)
  with pytest.raises(ValueError):
    next_delay(-1, 0)
  with pytest.raises(ValueError):
    next_delay(float('nan'), 0)


def test_cpu_and_wall_limits_preserve_stricter_existing_budget(monkeypatch):
  calls = []
  monkeypatch.setattr(resource, 'getrlimit', lambda _: (20, 25))
  monkeypatch.setattr(resource, 'setrlimit', lambda kind, value: calls.append((kind, value)))
  monkeypatch.setattr(signal, 'alarm', lambda seconds: calls.append(('alarm', seconds)))
  live.configure_worker_limits()
  assert calls == [(resource.RLIMIT_CPU, (20, 21)), ('alarm', 330)]


class FakeClock:
  def __init__(self):
    self.t = 100.0

  def clock(self):
    return self.t

  def clock_ns(self):
    return int(self.t * 1e9)

  def sleep(self, duration):
    self.t += duration


def test_arm_waits_for_continuous_offroad_and_launches_once(tmp_path):
  c, calls = FakeClock(), []
  arm_worker(lambda: True, lambda: calls.append('prepared'), lambda: calls.append('launched'), tmp_path,
             c.clock, c.clock_ns, c.sleep)
  assert c.t >= 115
  assert calls == ['prepared', 'launched']
  assert requested(tmp_path, c.clock_ns())
  with pytest.raises(RuntimeError, match='already armed'):
    arm_worker(lambda: True, lambda: None, lambda: None, tmp_path, c.clock, c.clock_ns, c.sleep)


def test_arm_never_launches_if_offroad_not_confirmed_or_lost_after_setup(tmp_path):
  c, calls = FakeClock(), []
  with pytest.raises(RuntimeError, match='not stable'):
    arm_worker(lambda: False, lambda: calls.append('prepared'), lambda: calls.append('launched'), tmp_path,
               c.clock, c.clock_ns, c.sleep)
  assert calls == [] and not (tmp_path / 'armed.json').exists()
  c, ok = FakeClock(), [True]

  def prepare():
    ok[0] = False

  with pytest.raises(RuntimeError, match='no longer confirmed'):
    arm_worker(lambda: ok[0], prepare, lambda: calls.append('launched'), tmp_path, c.clock, c.clock_ns, c.sleep)
  assert calls == [] and not (tmp_path / 'armed.json').exists()


def test_failed_launch_clears_arm(tmp_path):
  c = FakeClock()

  def fail():
    raise OSError('spawn failed')

  with pytest.raises(OSError, match='spawn failed'):
    arm_worker(lambda: True, lambda: None, fail, tmp_path, c.clock, c.clock_ns, c.sleep)
  assert not (tmp_path / 'armed.json').exists()


class Params:
  def __init__(self, onroad=True, shutdown=False):
    self.values = {'IsOnroad': onroad, 'IsOffroad': not onroad, 'DoShutdown': shutdown}

  def get_bool(self, key):
    return self.values.get(key, False)


class Messages:
  def __init__(self):
    self.seen = {'deviceState': True, 'modelV2': True}
    self.device = SimpleNamespace(started=True, thermalStatus='green')
    self.alive = True
    self.valid = True

  def __getitem__(self, name):
    assert name == 'deviceState'
    return self.device

  def all_alive(self, names):
    return self.alive

  def all_valid(self, names):
    return self.valid


def test_unhealthy_missing_stale_offroad_shutdown_or_heat_rejects():
  sm = Messages()
  assert healthy(Params(), sm)
  assert not healthy(Params(onroad=False), sm)
  assert not healthy(Params(shutdown=True), sm)
  sm.alive = False
  assert not healthy(Params(), sm)
  sm.alive, sm.valid = True, False
  assert not healthy(Params(), sm)
  sm.valid, sm.device.thermalStatus = True, 'yellow'
  assert not healthy(Params(), sm)
  sm.device.thermalStatus, sm.device.started = 'green', False
  assert not healthy(Params(), sm)
  sm.device.started, sm.seen['modelV2'] = True, False
  assert not healthy(Params(), sm)


def test_status_always_reports_zero_control_even_if_caller_disagrees(tmp_path):
  write_status(tmp_path, {'state': 'test', 'control_eligible': True, 'applied_offset_m': .15})
  out = json.loads((tmp_path / 'latest.json').read_text())
  assert out['control_eligible'] is False
  assert out['applied_offset_m'] == 0.0
  assert isinstance(out['updated_monotonic_ns'], int)


def test_status_hides_detections_after_disarm_timeout_or_future_timestamp(tmp_path):
  now = 50_000_000_000
  (tmp_path / 'armed.json').write_text(json.dumps({'version': 1, 'expires_monotonic_ns': now + 10_000_000_000}))
  latest = tmp_path / 'latest.json'
  sample = {'state': 'observing', 'updated_monotonic_ns': now - 1_000_000_000,
            'detections': [{'label': 'truck'}]}
  latest.write_text(json.dumps(sample))
  assert status_snapshot(tmp_path, now)['latest_fresh']
  assert status_snapshot(tmp_path, now)['latest']['detections']
  assert not status_snapshot(tmp_path, now + 4_000_000_000)['latest_fresh']
  assert status_snapshot(tmp_path, now + 4_000_000_000)['latest']['detections'] == []
  sample['updated_monotonic_ns'] = now + 1
  latest.write_text(json.dumps(sample))
  assert status_snapshot(tmp_path, now)['latest']['detections'] == []
  (tmp_path / 'armed.json').unlink()
  assert status_snapshot(tmp_path, now + 1)['latest']['detections'] == []


def test_letterbox_shape_and_transform():
  image = np.zeros((330, 526, 3), dtype=np.uint8)
  tensor, transform = letterbox_rgb(image)
  assert tensor.shape == (1, 3, 640, 640)
  assert tensor.dtype == np.float32
  assert transform[3:] == (526, 330)
  assert transform[1] == 0 and transform[2] > 0
  assert tensor[0, 0, 0, 0] == pytest.approx(114 / 255)


def test_detection_nms_is_class_aware_and_keeps_clipped_boxes_for_review():
  out = np.zeros((1, 14, 8400), dtype=np.float32)
  # Two almost identical trucks and one bus. Class-aware NMS retains the bus.
  for index, cls, score, x in [(0, 3, .9, 320), (1, 3, .8, 321), (2, 4, .7, 320), (3, 3, .6, 2)]:
    out[0, :4, index] = [x, 320, 100, 100]
    out[0, 4 + cls, index] = score
  result = decode_output(out, (1.0, 0, 0, 640, 640))
  assert [x['label'] for x in result] == ['truck', 'bus', 'truck']
  assert result[-1]['edge_clipped'] is True
  assert result[-1]['box'][0] == 0


def test_invalid_output_never_produces_detections():
  with pytest.raises(ValueError):
    decode_output(np.zeros((1, 14, 1)), (1, 0, 0, 640, 640))
  out = np.zeros((1, 14, 8400), dtype=np.float32)
  out[0, 4, 0] = np.nan
  with pytest.raises(ValueError):
    decode_output(out, (1, 0, 0, 640, 640))
  out[0, 4, 0] = 1.1
  with pytest.raises(ValueError):
    decode_output(out, (1, 0, 0, 640, 640))


@pytest.mark.parametrize('healthy_after_inference', [True, False])
def test_live_frame_processing_fails_closed_when_health_is_lost(tmp_path, monkeypatch, healthy_after_inference):
  active, events, runs = [True], [], []
  monkeypatch.setattr(live, 'RUN_DIR', tmp_path)
  monkeypatch.setattr(live, 'requested', lambda: active[0])
  monkeypatch.setattr(live, 'configure_worker_scheduling', lambda: None)
  monkeypatch.setattr(live, 'configure_worker_limits', lambda: None)
  monkeypatch.setattr(live, 'wait_or_disarm', lambda _: None)
  health = iter([True, healthy_after_inference])
  monkeypatch.setattr(live, 'healthy', lambda *_: next(health))

  output = np.zeros((1, 14, 8400), dtype=np.float32)
  output[0, :4, 0] = [320, 320, 100, 100]
  output[0, 7, 0] = .9

  class Session:
    def run(self, *args):
      runs.append(True)
      return [output]

  monkeypatch.setattr(live, 'load_session', lambda: (Session(), 'test'))
  frame = SimpleNamespace(frame_id=7, data=b'', width=64, height=64, stride=64, uv_offset=4096)

  class Client:
    frame_id = 7

    def __init__(self, *_):
      self.timestamp_eof = time.monotonic_ns()

    def is_connected(self):
      return True

    def recv(self, **_):
      self.timestamp_eof = time.monotonic_ns()
      return frame

  vipc = ModuleType('msgq.visionipc')
  vipc.VisionIpcClient = Client
  vipc.VisionStreamType = SimpleNamespace(VISION_STREAM_ROAD=1)
  msgq = ModuleType('msgq')
  msgq.visionipc = vipc

  messaging = ModuleType('openpilot.cereal.messaging')
  messaging.SubMaster = lambda _: SimpleNamespace(update=lambda _: None)
  cereal = ModuleType('openpilot.cereal')
  cereal.messaging = messaging
  params = ModuleType('openpilot.common.params')
  params.Params = lambda: object()

  def event(name, **record):
    events.append((name, record))
    active[0] = False

  swaglog = ModuleType('openpilot.common.swaglog')
  swaglog.cloudlog = SimpleNamespace(event=event)
  common = ModuleType('openpilot.common')
  common.__path__ = []
  common.params, common.swaglog = params, swaglog
  signal_shadow = ModuleType('openpilot.selfdrive.modeld.signal_color_shadow')
  signal_shadow.rgb_from_nv12 = lambda *_: np.zeros((64, 64, 3), dtype=np.uint8)
  modeld = ModuleType('openpilot.selfdrive.modeld')
  modeld.__path__ = []
  modeld.signal_color_shadow = signal_shadow
  selfdrive = ModuleType('openpilot.selfdrive')
  selfdrive.__path__ = []
  selfdrive.modeld = modeld

  for name, module in [('msgq', msgq), ('msgq.visionipc', vipc), ('openpilot.cereal', cereal),
                       ('openpilot.cereal.messaging', messaging), ('openpilot.common', common),
                       ('openpilot.common.params', params), ('openpilot.common.swaglog', swaglog),
                       ('openpilot.selfdrive', selfdrive), ('openpilot.selfdrive.modeld', modeld),
                       ('openpilot.selfdrive.modeld.signal_color_shadow', signal_shadow)]:
    monkeypatch.setitem(sys.modules, name, module)
  live.run()
  record = json.loads((tmp_path / 'latest.json').read_text())
  assert len(runs) == 1 and len(events) == 1
  assert record['control_eligible'] is False and record['applied_offset_m'] == 0.0
  assert record['state'] == ('observing' if healthy_after_inference else 'stale_or_unhealthy')
  assert bool(record['detections']) is healthy_after_inference
