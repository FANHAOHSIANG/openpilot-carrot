import io
from dataclasses import replace
import pytest
from PIL import Image
from openpilot.selfdrive.carrot import map_hud
from openpilot.selfdrive.carrot.carrot_navi import CarrotNaviReceiver, CATALOG
from openpilot.selfdrive.carrot.carrot_navi_cereal import build_carrot_navi_media_payload


def connected_receiver():
  receiver = CarrotNaviReceiver()
  receiver.control_connected()
  receiver.negotiate({'type': 'requirements_query', 'protocol_version': 2, 'catalog_revision': 1,
                      'streams': [{'kind': k, 'name': n, 'schema_version': 1} for k, n in CATALOG]}, 'amap_auto_1.0')
  return receiver


def config(url='http://192.168.1.20:8080', **changes):
  return map_hud.normalize_config({'enabled': True, 'frame_url': url, 'fps': 2, **changes})


def test_base_url_normalizes_to_frame():
  assert config()['frame_url'] == 'http://192.168.1.20:8080/frame'


@pytest.mark.parametrize('url', ['http://127.0.0.1:8080', 'http://0.0.0.0:8080', 'http://8.8.8.8:8080',
                               'http://192.168.1.1', 'http://user:pass@192.168.1.1:80',
                               'https://192.168.1.1:80', 'http://192.168.1.1:80/stream',
                               'http://192.168.1.1:80/frame?x=1', 'http://224.0.0.1:8080'])
def test_rejects_non_projection_urls(url):
  with pytest.raises(ValueError):
    config(url)


@pytest.mark.parametrize('fps', [0, 6, True, '2'])
def test_invalid_refresh(fps):
  with pytest.raises(ValueError):
    config(fps=fps)


def test_jpeg_is_resized_with_transport_budget():
  image = Image.new('RGB', (1920, 1080), '#5599aa')
  buf = io.BytesIO()
  image.save(buf, 'JPEG')
  data, width, height = map_hud.prepare_jpeg(buf.getvalue())
  assert width <= 800 and height <= 480 and len(data) <= map_hud.MAX_OUTPUT_BYTES
  with Image.open(io.BytesIO(data)) as decoded:
    assert decoded.size == (width, height)


def test_non_jpeg_rejected():
  buf = io.BytesIO()
  Image.new('RGB', (10, 10)).save(buf, 'PNG')
  with pytest.raises(ValueError):
    map_hud.prepare_jpeg(buf.getvalue())


def test_projection_uses_existing_media_without_touching_navigation():
  receiver = connected_receiver()
  snapshot = receiver.cereal_snapshot()
  sid = snapshot['session_id']
  assert receiver.record_projection_frame(sid, (b'jpeg', 800, 450))
  assert receiver.cereal_snapshot() == snapshot
  records = receiver.drain_media_updates()
  payload = build_carrot_navi_media_payload(records[0], sid)
  assert payload['kind'] == 'render' and payload['name'] == 'map_main'
  assert payload['messageType'] == 1 and payload['formatOrReason'] == 2
  assert payload['present'] and payload['payload'] == b'jpeg'
  assert receiver.record_projection_frame(sid, None)
  clear = receiver.drain_media_updates()[0]
  assert not clear.present and clear.message_type == 4


def test_rejects_session_change_and_keeps_native_map():
  receiver = connected_receiver()
  sid = receiver.cereal_snapshot()['session_id']
  assert not receiver.record_projection_frame('wrong-session', (b'jpeg', 20, 20))
  assert receiver.record_projection_frame(sid, (b'jpeg', 20, 20))
  receiver.drain_media_updates()
  receiver._records['render:map_main'] = replace(receiver._records['render:map_main'], peer='native-phone')
  assert not receiver.record_projection_frame(sid, (b'other', 20, 20))
  assert not receiver.record_projection_frame(sid, None)
  assert not receiver.drain_media_updates()


def test_disabled_never_fetches_and_waits_for_navigation():
  receiver = CarrotNaviReceiver()
  bridge = map_hud.MapHudBridge(receiver, fetch=lambda _: pytest.fail('unexpected fetch'))
  assert bridge.tick(dict(map_hud.DEFAULT_CONFIG))['state'] == 'disabled'
  assert bridge.tick(config())['state'] == 'waiting_navigation'


def test_duplicate_frames_expire_and_source_error_clears(monkeypatch):
  now = [10.0]
  monkeypatch.setattr(map_hud.time, 'monotonic', lambda: now[0])
  receiver = connected_receiver()
  bridge = map_hud.MapHudBridge(receiver, fetch=lambda _: (b'jpeg', '1'), prepare=lambda _: (b'jpeg', 40, 20))
  assert bridge.tick(config())['state'] == 'streaming'
  assert len(receiver.drain_media_updates()) == 1
  now[0] += 1
  assert bridge.tick(config())['state'] == 'streaming'
  assert receiver.drain_media_updates() == []
  now[0] += 3
  assert bridge.tick(config())['state'] == 'stalled'
  assert not receiver.drain_media_updates()[0].present
  bridge.fetch = lambda _: (b'jpeg2', '2')
  assert bridge.tick(config())['state'] == 'streaming'
  receiver.drain_media_updates()
  now[0] += 4
  def fail(_):
    raise OSError('source gone')
  bridge.fetch = fail
  assert bridge.tick(config())['state'] == 'source_error'
  assert not receiver.drain_media_updates()[0].present


def test_disable_clears_previous_map():
  receiver = connected_receiver()
  bridge = map_hud.MapHudBridge(receiver, fetch=lambda _: (b'jpeg', '1'), prepare=lambda _: (b'jpeg', 40, 20))
  bridge.tick(config())
  receiver.drain_media_updates()
  assert bridge.tick(config(enabled=False))['state'] == 'disabled'
  assert not receiver.drain_media_updates()[0].present


def test_projection_reaches_real_hud_media_parser():
  import sys
  from pathlib import Path
  from types import SimpleNamespace
  sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cluster'))
  from cluster_navi_source import NaviIpcMediaSource
  receiver = connected_receiver()
  sid = receiver.cereal_snapshot()['session_id']
  buf = io.BytesIO()
  Image.new('RGB', (1200, 700), '#334455').save(buf, 'JPEG')
  bridge = map_hud.MapHudBridge(receiver, fetch=lambda _: (buf.getvalue(), '1'))
  assert bridge.tick(config())['state'] == 'streaming'
  pending = []
  for record in receiver.drain_media_updates():
    pending.append(SimpleNamespace(carrotNaviMedia=SimpleNamespace(**build_carrot_navi_media_payload(record, sid))))
  class Messaging:
    def sub_sock(self, *args, **kwargs):
      return SimpleNamespace(close=lambda: None)
    def drain_sock(self, _socket):
      result = list(pending)
      pending.clear()
      return result
  source = NaviIpcMediaSource(Messaging())
  try:
    dashboard = source.update(None)
    frame = next(x for x in dashboard.media if x.key == 'render:map_main')
    assert frame.present and frame.mime == 'image/jpeg'
    with Image.open(io.BytesIO(frame.data)) as image:
      assert image.width <= 800 and image.height <= 480
    bridge.tick(config(enabled=False))
    record = receiver.drain_media_updates()[0]
    pending.append(SimpleNamespace(carrotNaviMedia=SimpleNamespace(**build_carrot_navi_media_payload(record, sid))))
    dashboard = source.update(None)
    assert not next(x for x in dashboard.media if x.key == 'render:map_main').present
  finally:
    source.close()


def test_fetch_frame_reads_cp_projection_http():
  from http.server import BaseHTTPRequestHandler, HTTPServer
  import threading
  buf = io.BytesIO()
  Image.new('RGB', (100, 60)).save(buf, 'JPEG')
  jpeg = buf.getvalue()
  class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
      assert self.path == '/frame'
      self.send_response(200)
      self.send_header('Content-Type', 'image/jpeg')
      self.send_header('Content-Length', str(len(jpeg)))
      self.send_header('X-Frame-Sequence', '42')
      self.end_headers()
      self.wfile.write(jpeg)
    def log_message(self, *args):
      pass
  server = HTTPServer(('127.0.0.1', 0), Handler)
  worker = threading.Thread(target=server.serve_forever, daemon=True)
  worker.start()
  try:
    data, identity = map_hud.fetch_frame(f'http://127.0.0.1:{server.server_port}/frame')
    assert data == jpeg and identity.startswith('42:')
  finally:
    server.shutdown()
    server.server_close()
    worker.join(timeout=1)


def test_settings_api_persists_and_rejects_invalid_source(tmp_path, monkeypatch):
  import asyncio
  from aiohttp import web
  from aiohttp.test_utils import TestClient, TestServer
  import importlib.util
  from pathlib import Path
  path = Path(__file__).resolve().parents[1] / 'server/features/map_hud.py'
  spec = importlib.util.spec_from_file_location('map_hud_feature_test', path)
  feature = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(feature)
  monkeypatch.setattr(map_hud, 'CONFIG_PATH', tmp_path / 'config.json')
  async def exercise():
    app = web.Application()
    feature.register(app)
    async with TestClient(TestServer(app)) as client:
      response = await client.post('/api/map_hud', json={'enabled': True, 'frame_url': 'http://192.168.1.20:8080', 'fps': 2})
      assert response.status == 200
      assert map_hud.read_config() == config()
      response = await client.post('/api/map_hud', json={'enabled': True, 'frame_url': 'http://8.8.8.8:80', 'fps': 2})
      assert response.status == 400 and map_hud.read_config() == config()
      response = await client.get('/map-hud')
      assert response.status == 200 and 'CP' in await response.text()
  asyncio.run(exercise())
