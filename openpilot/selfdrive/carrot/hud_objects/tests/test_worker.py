import json
import os
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from openpilot.selfdrive.carrot.hud_objects import worker
from openpilot.selfdrive.carrot.xiaoge.nv12 import pack_nv12


def batch(kind, stamp, camera='road'):
  return {'camera': camera, 't': stamp, 'objects': [[kind, .5, .8, .3, .4, .9]] if kind else []}


class FakeInference:
  def __init__(self):
    self.pipe = Mock()
    self.pipe.poll.return_value = False
    self.process = Mock()
    self.process.is_alive.return_value = True
    self.closed = False

  def close(self):
    self.closed = True


@pytest.fixture
def setup(tmp_path):
  child = FakeInference()
  w = worker.Worker(worker.Output(tmp_path/'hud'), tmp_path/'shared', factory=Mock(return_value=child), warn=Mock())
  return w, child


def publish_result(w, child, now, result, cpu=.005, error=None, reuse=False):
  child.pipe.poll.return_value = True
  child.pipe.recv.return_value = result, cpu, error
  w.tick(now, True, reuse)
  child.pipe.poll.return_value = False


def snapshot(w):
  return json.loads(w.output.path.read_bytes())


def test_independent_captures_and_latest_only(setup):
  w, child = setup
  w.tick(20., True, False)
  w.tick(20.05, True, False)
  child.pipe.send.assert_called_once_with('traffic')
  publish_result(w, child, 20.2, batch('car', 20.08))
  assert snapshot(w)['objects'][0][0] == 'car'
  w.tick(20.4, True, False)
  assert child.pipe.send.call_args.args == ('cone',)
  publish_result(w, child, 20.55, batch('cone', 20.49))
  assert [b['t'] for b in snapshot(w)['batches']] == [20.08, 20.49]
  w.tick(20.72, True, False)
  publish_result(w, child, 20.90, batch(None, 20.8))
  assert snapshot(w)['objects'] == []
  assert [b['objects'] for b in snapshot(w)['batches']] == [batch('cone', 20.49)['objects'], []]
  w.tick(21.9, True, False)
  assert snapshot(w)['batches'] == []


def test_wide_reuse_only_if_no_fresh_narrow_observation(setup):
  w, child = setup
  w.tick(10., True, False)
  w.shared.write_text(json.dumps({'version': 1, **batch('bus', 10.02, 'wideRoad')}))
  w.tick(10.10, True, True)
  assert not child.closed and w.pending == 'traffic'
  assert snapshot(w)['camera'] == 'wideRoad'
  publish_result(w, child, 10.25, batch(None, 10.18), reuse=True)
  assert snapshot(w)['camera'] == 'road' and snapshot(w)['objects'] == []
  w.tick(10.45, True, True)
  assert w.pending == 'cone'
  publish_result(w, child, 10.6, batch('cone', 10.5), reuse=True)
  assert [b['camera'] for b in snapshot(w)['batches']] == ['road', 'road']
  w.shared.write_text(json.dumps({'version': 1, **batch('car', 11.1, 'wideRoad')}))
  w.tick(11.21, True, True)
  assert [b['camera'] for b in snapshot(w)['batches']] == ['road', 'wideRoad']
  assert w.pending == 'traffic'
  w.tick(11.30, True, False)
  assert [b['camera'] for b in snapshot(w)['batches']] == ['road']
  assert not child.closed


def test_heat_stop_clears_inflight_and_waits_before_resuming_shared_output(setup):
  w, child = setup
  w.tick(30, True, False)
  w.tick(30.1, False, True)
  assert child.closed and not snapshot(w)['objects']
  w.shared.write_text(json.dumps({'version': 1, **batch('bus', 32.9, 'wideRoad')}))
  w.tick(33.0, True, True)
  assert w.pending is None and not snapshot(w)['objects']
  w.tick(33.2, True, True)
  assert w.pending in ('traffic','cone') and snapshot(w)['t'] == 32.9


def test_busy_cpus_only_reuse_fresh_wide_result_and_never_launch_inference(setup):
  w, child = setup
  w.tick(20., True, False)
  w.shared.write_text(json.dumps({'version': 1, **batch('truck', 20.1, 'wideRoad')}))
  w.tick(20.2, True, True, cpu_busy=True)
  assert child.closed and w.pending is None
  assert snapshot(w)['batches'] == [batch('truck', 20.1, 'wideRoad')]
  w.tick(20.4, True, False, cpu_busy=True)
  assert snapshot(w)['batches'] == []
  w.tick(21.2, True, True, cpu_busy=True)
  assert snapshot(w)['batches'] == []
  w.tick(23., True, True)
  w.factory.assert_called_once()
  w.tick(24.3, True, True)
  assert w.pending is not None and w.factory.call_count == 2


def test_timeout_of_one_model_leaves_other_available_after_backoff(setup):
  w, child = setup
  w.tick(10, True, False)
  w.tick(20, True, False)
  assert child.closed and not snapshot(w)['objects']
  w.tick(23.1, True, False)
  assert w.pending == 'cone'


def test_late_batch_never_published_and_cpu_cost_slows_next_attempt(setup):
  w, child = setup
  w.tick(10, True, False)
  publish_result(w, child, 11.1, batch('truck', 10.05), cpu=.5)
  assert not snapshot(w)['objects']
  w.tick(14, True, False)
  child.pipe.send.assert_called_once()
  w.tick(14.2, True, False)
  assert w.pending == 'cone'


def test_bad_or_stale_shared_data_fails_closed_and_fifo_does_not_block(tmp_path):
  p = tmp_path/'shared'
  for record in (dict(batch('bus', 10., 'wideRoad'), version=1), dict(batch('bus', 10., 'road'), version=1),
                 dict(batch('cone', 10., 'wideRoad'), version=1), {'version': True}, []):
    p.write_text(json.dumps(record))
    assert not worker.wide_observation(p, 11.)
  p.write_bytes(b'[' * 20000)
  assert not worker.wide_observation(p, 10.)
  p.unlink()
  os.mkfifo(p)
  assert not worker.wide_observation(p, 10.)


def test_camera_reads_only_new_unreused_visible_nv12_planes(monkeypatch):
  monkeypatch.setattr(worker, 'capture_monotonic', lambda _: 8.)
  monkeypatch.setattr(worker.time, 'monotonic', lambda: 8.1)
  client = Mock(frame_id=9, timestamp_eof=123)
  buf = SimpleNamespace(frame_id=9, width=2, height=2, stride=4, uv_offset=12, data=bytes(range(16)))
  client.recv.return_value = buf
  result = worker.read_camera(client, None, pack_nv12, lambda arr: arr)
  assert result[:2] == ((9,123),8.)
  np.testing.assert_array_equal(result[2], [[0,1],[4,5],[12,13]])
  assert worker.read_camera(client, (9,123), pack_nv12, lambda _: None) is None
  buf.frame_id = 10
  assert worker.read_camera(client, None, pack_nv12, lambda _: None) is None
  buf.frame_id = 9
  monkeypatch.setattr(worker.time, 'monotonic', lambda: 8.25)
  assert worker.read_camera(client, None, pack_nv12, lambda _: None) is None


class State(dict):
  valid = True

  def all_alive(self, _services):
    return self.valid

  def all_valid(self, _services):
    return self.valid


def test_main_model_prioritized_on_lag_heat_memory_load_display_disconnect(monkeypatch):
  monkeypatch.setattr(worker.time, 'clock_gettime', lambda _: 6.1)
  params = Mock()
  enabled = {'C4HudObjects', 'C4HudUsbConnected', 'IsOnroad'}
  params.get_bool.side_effect = lambda key: key in enabled
  params.get_int.return_value = 1
  model = SimpleNamespace(timestampEof=6_000_000_000, modelExecutionTime=.035, frameDropPerc=0)
  dev = SimpleNamespace(cpuUsagePercent=[40]*8, memoryUsagePercent=70, started=True, thermalStatus='green')
  sm = State(modelV2=model, deviceState=dev)
  assert worker.suspension_reason(sm, params) is None
  for obj, key, value in [(model,'timestampEof',4_000_000_000), (model,'modelExecutionTime',.08), (model,'frameDropPerc',1.01),
                          (dev,'thermalStatus','yellow'), (dev,'memoryUsagePercent',94), (dev,'cpuUsagePercent',[])]:
    orig = getattr(obj,key)
    setattr(obj,key,value)
    assert worker.suspension_reason(sm, params)
    setattr(obj,key,orig)
  # Saturation on the child's permitted little cores allows only passive display.
  dev.cpuUsagePercent = [94, 95, 95, 95, 100, 100, 100, 100]
  assert worker.suspension_reason(sm, params) is None
  dev.cpuUsagePercent[0] = 95
  assert worker.suspension_reason(sm, params) == worker.CPU_BUSY
  dev.cpuUsagePercent[0] = 96
  assert worker.suspension_reason(sm, params) == worker.CPU_BUSY
  dev.cpuUsagePercent = [100, 100, 10, 10, 20, 20, 20, 20]
  assert worker.suspension_reason(sm, params, {0, 1}) == worker.CPU_BUSY
  assert worker.suspension_reason(sm, params, {2, 3}) is None
  assert worker.suspension_reason(sm, params, set()) not in (None, worker.CPU_BUSY)
  for obj, key, value in [(dev, 'thermalStatus', 'yellow'), (dev, 'memoryUsagePercent', 90), (model, 'modelExecutionTime', .051)]:
    before = getattr(obj, key)
    setattr(obj, key, value)
    assert worker.suspension_reason(sm, params, {0, 1}) not in (None, worker.CPU_BUSY)
    setattr(obj, key, before)
  enabled.add('UsbGpuLoading')
  assert worker.suspension_reason(sm, params)
  enabled.remove('UsbGpuLoading')
  enabled.remove('C4HudUsbConnected')
  assert worker.suspension_reason(sm, params)


def test_rlog_records_each_published_detector_capture_once(tmp_path):
  report = Mock()
  output = worker.Output(tmp_path / 'hud', report=report)
  road = dict(batch('motorcycle', 19.9), frame_id=321, timestamp_eof_ns=29_900_000_000)
  output.write({'traffic': road}, 20.)
  output.write({'traffic': road}, 20.02)
  cone = batch(None, 19.95)
  output.write({'cone': cone, 'traffic': road}, 20.03)
  wide = batch('car', 20.04, 'wideRoad')
  output.write({'traffic': wide}, 20.05)
  output.write({}, 20.06)
  output.write({'traffic': road}, 20.07)
  output.write({'traffic': batch('person', 20.)}, 21.)
  assert [call.args for call in report.call_args_list] == [('c4HudObjectsFrame',)] * 3
  motor, empty, reused = [call.kwargs for call in report.call_args_list]
  assert motor == {'camera': 'road', 'detector': 'traffic', 'count': 1, 'age_ms': 100,
                   'objects': [['motorcycle', .5, .8, .3, .4, .9]], 'frame_id': 321, 'timestamp_eof_ns': 29_900_000_000}
  assert (empty['detector'], empty['objects'], empty['count']) == ('cone', [], 0)
  assert (reused['camera'], reused['objects'][0][0], reused['frame_id']) == ('wideRoad', 'car', None)


def test_rlog_state_survives_short_suspensions_and_reports_healthy_or_idle_segments():
  report = Mock()
  log = worker.StatusLog(report)
  for t, reason in [(10., None), (11., worker.CPU_BUSY), (12., 'device stopped or warm'), (15., None), (20., None)]:
    log.update(t, reason, 'waiting')
  states = [call.kwargs for call in report.call_args_list]
  assert len(states) == 3 and all(call.args == ('c4HudObjectsState',) for call in report.call_args_list)
  assert states[0]['gate_samples'] == states[2]['gate_samples'] == {'ready': 1}
  assert states[1] == {'gate': 'ready', 'status': 'waiting',
                       'gate_samples': {worker.CPU_BUSY: 1, 'device stopped or warm': 1, 'ready': 1}}


def test_shared_camera_metadata_is_optional_and_only_copies_integer_fields(tmp_path):
  path = tmp_path / 'wide'
  row = dict(batch('car', 10., 'wideRoad'), version=1, frame_id=1943, timestamp_eof_ns=10_000_000_000)
  path.write_text(json.dumps(row))
  record = worker.wide_observation(path, 10.2)
  assert (record['frame_id'], record['timestamp_eof_ns']) == (1943, 10_000_000_000)
  row.update(frame_id=True, timestamp_eof_ns={'value': 'invalid'})
  path.write_text(json.dumps(row))
  assert worker.wide_observation(path, 10.2) == batch('car', 10., 'wideRoad')
