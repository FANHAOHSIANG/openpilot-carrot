import base64
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import hud_protocol as p
from hud_camera import preview_nv12, WIDTH, HEIGHT


def test_preview_preserves_full_camera_field_and_uv_order():
  width, height, stride = WIDTH * 2, HEIGHT * 2, WIDTH * 2 + 16
  y = np.arange(height * stride, dtype=np.uint8).reshape(height, stride)
  uv = np.zeros((height // 2, stride), np.uint8)
  uv[:, 0::2] = 71
  uv[:, 1::2] = 183
  frame = SimpleNamespace(width=width, height=height, stride=stride, uv_offset=height * stride,
                          data=y.tobytes() + uv.tobytes() + b'padding beyond NV12 planes')
  out = np.frombuffer(preview_nv12(frame), np.uint8)
  np.testing.assert_array_equal(out[:WIDTH * HEIGHT].reshape(HEIGHT, WIDTH), y[::2, :width:2])
  assert np.all(out[WIDTH * HEIGHT::2] == 71)
  assert np.all(out[WIDTH * HEIGHT + 1::2] == 183)


def test_stale_and_oversized_display_data_are_not_shown(tmp_path, monkeypatch):
  path = tmp_path / 'hud'
  monkeypatch.setattr(p, 'HUD_PACKET', path)
  monkeypatch.setattr(p.time, 'monotonic', lambda: 10.)
  for data in (p.HEADER.pack(9.) + b'{"version":1}', b'x' * (p.MAX_HUD_BYTES + 20), b'bad'):
    path.write_bytes(data)
    monkeypatch.setattr(p, '_next_snapshot_read', 0.)
    assert p.read_snapshot() is None
  path.write_bytes(p.HEADER.pack(9.9) + json.dumps({'version':1, 'params':{}}).encode())
  monkeypatch.setattr(p, '_next_snapshot_read', 0.)
  assert p.read_snapshot()[1]['version'] == 1


def test_publisher_does_not_replay_stale_or_duplicate_snapshots(tmp_path, monkeypatch):
  publisher = object.__new__(p.Publisher)
  publisher.path = tmp_path / 'publisher'
  publisher.last_sent = 0.
  monkeypatch.setattr(p.time, 'monotonic', lambda: 10.)
  assert publisher.packet() is None
  publisher.path.write_bytes(p.HEADER.pack(9.9) + b'latest')
  assert publisher.packet() == b'latest'
  assert publisher.packet() is None
  publisher.path.write_bytes(p.HEADER.pack(8.) + b'stale')
  assert publisher.packet() is None
  publisher.path.write_bytes(p.HEADER.pack(9.99) + b'x' * (96 * 1024 + 1))
  assert publisher.packet() is None


def test_snapshot_sends_fresh_instrument_sign_after_updating_submaster(monkeypatch):
  from openpilot.cereal import car
  import hud_signal
  from openpilot.common import indicator_display, jetlink_status

  cs = car.CarState.new_message(canValid=True, speedLimitClusterKph=80)
  clock = [10.]

  class SubMaster(dict):
    def update(self, _timeout):
      clock[0] += .002
      if self.updated['carState']:
        self.recv_time['carState'] = clock[0]

  sm = SubMaster(carState=cs)
  sm.valid = {'carState': True}
  sm.alive = {'carState': True}
  sm.updated = {'carState': True}
  sm.logMonoTime = {'carState': int(clock[0] * 1e9)}
  sm.recv_time = {}
  builder = object.__new__(p.SnapshotBuilder)
  builder.sm = sm
  builder.cached = {}
  builder.settings = {}
  builder.host_release = builder.nav_map = None
  builder.network = SimpleNamespace(address=lambda: '')
  builder.camera_previews = dict
  builder.next_send = 0.
  builder.next_params = 20.
  monkeypatch.setattr(p, 'SERVICES', ('carState',))
  monkeypatch.setattr(p.time, 'monotonic', lambda: clock[0])
  monkeypatch.setattr(jetlink_status, 'badge', lambda: None)
  monkeypatch.setattr(hud_signal, 'signal_packet', lambda _now: {})
  monkeypatch.setattr(indicator_display, 'current', lambda: {})

  def snapshot():
    clock[0] += .2
    return json.loads(builder.packet())

  assert snapshot()['cluster_speed_limit_kph'] == 80
  sm.updated['carState'] = False
  clock[0] += .6
  assert 'cluster_speed_limit_kph' not in snapshot()
  sm.updated['carState'] = True
  sm.valid['carState'] = False
  assert 'cluster_speed_limit_kph' not in snapshot()
