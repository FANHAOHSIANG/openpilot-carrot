import base64
from io import BytesIO
import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace as NS

import numpy as np
from PIL import Image
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(Path(__file__).parent), str(ROOT / 'openpilot/selfdrive/carrot/cluster')]
from yolo.core import CLASSES, decode, ground_position, is_rider, letterbox
from yolo.transport import Frames, read_packet, write_result, calibration
from hud_yolo import result_for
from cluster_yolo_overlay import ObjectOverlay, valid_result, glyph_lines


def packet():
  output = BytesIO()
  Image.new('RGB', (384, 240), (180, 90, 20)).save(output, format='JPEG')
  return {'version': 1, 'sent': 100., 'params': {'IsOnroad': 'MQ=='},
          'cameras': {'road': {'frame': 5, 'capture_time': 99.9, 'time': 99.95,
                               'source_width': 1344, 'source_height': 760, 'width': 384, 'height': 240,
                               'jpeg': base64.b64encode(output.getvalue()).decode()}}}


def result():
  return {'version': 1, 'mode': 'live', 'status': 'ready', 'written_mono': 10.1,
          'captured_mono': 10., 'expires_mono': 10.8, 'frame_id': 5,
          'source_width': 1344, 'source_height': 760, 'objects': [
            {'cls': 3, 'name': 'motorcycle', 'conf': .9, 'box': [.2, .3, .4, .7],
             'd': 11., 'lat': -2., 'range_source': 'monocular_estimate'}]}


def test_letterbox_and_inverse_recover_nonsquare_full_frame():
  rgb = np.zeros((760, 1344, 3), np.uint8)
  x, transform = letterbox(rgb, 672, 384)
  assert x.shape == (1, 3, 384, 672)
  assert transform == (.5, .5, 0, 2)
  out = np.zeros((1, 84, 1), np.float32)
  out[0, :4, 0] = [336, 192, 336, 190]
  out[0, 6, 0] = .9
  det = decode(out, transform, (1344, 760), {c: c for c in CLASSES})
  np.testing.assert_allclose(det[0]['box'], [.25, .25, .75, .75])


def test_six_classes_nms_rider_dedup_and_invalid_scores():
  out = np.zeros((1, 84, 9), np.float32)
  for i, c in enumerate([0, 1, 2, 3, 5, 7, 2, 9, 0]):
    out[0, :4, i] = [30+i*65, 180, 40, 80]
    out[0, 4+c, i] = .9
  out[0, :4, 6] = out[0, :4, 2]  # Duplicate car.
  out[0, 4, 8] = np.nan
  dets = decode(out, (1, 1, 0, 0), (672, 384), {c: c for c in CLASSES})
  assert {d['cls'] for d in dets} == set(CLASSES)
  assert len(dets) == 6
  assert is_rider([.4, .1, .6, .6], [.35, .5, .65, .8])
  assert not is_rider([.05, .1, .2, .6], [.35, .5, .65, .8])
  out = np.zeros((1, 84, 2), np.float32)
  out[0, :4, 0], out[0, 4, 0] = [336, 130, 100, 140], .9
  out[0, :4, 1], out[0, 7, 1] = [336, 240, 160, 100], .9
  assert [d['cls'] for d in decode(out, (1, 1, 0, 0), (672, 384), {c:c for c in CLASSES})] == [3]


def test_metric_projection_uses_vehicle_height_and_handles_roll():
  camera = {'width': 1344, 'height': 760, 'focal': 1141.5, 'height_m': 1.4, 'rpy': [0, 0, 0]}
  # A ground point 20 m forward, 2 m right in the calibrated narrow image.
  cx = .5 + (2/20)*1141.5/1344
  bottom = .5 + (1.4/20)*1141.5/760
  pos = ground_position([cx-.02, .4, cx+.02, bottom], camera)
  assert pos == {'d': 20., 'lat': 2., 'range_source': 'monocular_estimate'}
  assert ground_position([.4, .4, .6, .99], camera) is None
  assert ground_position([.4, .1, .6, .2], camera) is None
  assert ground_position([.4, .1, .6, .6], {**camera, 'height_m': float('nan')}) is None
  camera['rpy'] = [.08, -.04, .06]
  # Compare with this repository's road-to-view projection, when its native helper is available.
  from openpilot.common.transformations.camera import get_view_frame_from_road_frame
  projected = get_view_frame_from_road_frame(*camera['rpy'], camera['height_m']) @ np.array([20, -2, 0, 1])
  x = .5 + projected[0]/projected[2]*camera['focal']/1344
  y = .5 + projected[1]/projected[2]*camera['focal']/760
  assert ground_position([x-.02, y-.1, x+.02, y], camera) == pos


@pytest.mark.parametrize('change', ['stale', 'future', 'dimension', 'jpeg', 'offroad', 'oversized'])
def test_bad_or_old_camera_frames_are_rejected(change):
  p = packet()
  frame = p['cameras']['road']
  if change == 'stale': frame['capture_time'] = 99.
  if change == 'future': frame['capture_time'] = 101.
  if change == 'dimension': frame['width'] = 672
  if change == 'jpeg': frame['jpeg'] = '***'
  if change == 'offroad': p['params']['IsOnroad'] = 'MA=='
  if change == 'oversized': frame['jpeg'] = 'a'*280001
  assert Frames().take((10., p), 10.1) is None


def test_frozen_camera_cannot_renew_result_via_new_transport_packets(tmp_path):
  p = packet()
  path = tmp_path/'packet'
  path.write_bytes(struct.pack('<d', 10.) + json.dumps(p).encode())
  snapshot = read_packet(path, 10.1)
  frames = Frames()
  frame = frames.take(snapshot, 10.1)
  assert frame['captured_mono'] == pytest.approx(9.9)
  assert frame['resolution'] == [384, 240]
  assert frames.take((10.2, p), 10.25) is None
  assert read_packet(path, 10.6) is None
  path.write_bytes(b'x'*524289)
  assert read_packet(path, 10.1) is None


@pytest.mark.parametrize('change', ['expired', 'future', 'nan', 'badclass', 'many', 'offline', 'uncalibrated_range'])
def test_overlay_fails_closed_on_bad_or_expired_results(change):
  r = result()
  now = 10.2
  if change == 'expired': now = 10.81
  if change == 'future': r['captured_mono'] = 11.
  if change == 'nan': r['objects'][0]['box'][0] = float('nan')
  if change == 'badclass': r['objects'][0]['cls'] = 80
  if change == 'many': r['objects'] *= 33
  if change == 'offline': r['mode'] = 'offline'
  if change == 'uncalibrated_range': r['objects'][0]['range_source'] = 'guess'
  assert valid_result(r, now) is None


def test_disabled_overlay_does_no_io_and_cache_still_expires(tmp_path, monkeypatch):
  assert ObjectOverlay().read(10.2) is None
  path = tmp_path/'result'
  write_result(path, result())
  reader = ObjectOverlay(path)
  assert reader.read(10.2)
  reader.next_read = 99.
  assert reader.read(10.81) is None
  assert len({str(glyph_lines(c)) for c in CLASSES}) >= 4


def test_late_inference_is_discarded_and_no_calibration_never_invents_distance():
  frame = Frames().take((10., packet()), 10.1)
  detector = NS(sha256='abc', detect=lambda rgb: [{'cls': 0, 'name': 'person', 'conf': .9, 'box': [.1, .2, .2, .7]}])
  clock = iter([10.1, 10.2])
  r = result_for(detector, frame, None, lambda: next(clock))
  assert r['status'] == 'ready' and 'd' not in r['objects'][0]
  clock = iter([10.1, 11.])
  r = result_for(detector, frame, None, lambda: next(clock))
  assert r['status'] == 'late' and not r['objects']


def test_calibration_requires_fresh_valid_carrot_profile(monkeypatch):
  import yolo.transport as transport
  events = {'liveCalibration': {'calStatus': 'calibrated', 'rpyCalib': [0, 0, 0], 'height': [1.4]},
            'deviceState': {'deviceType': 'mici'}, 'roadCameraState': {'sensor': 'os04c10'}}
  monkeypatch.setattr(transport, 'event_data', lambda packet, name, age: events.get(name))
  frame = {'source_width': 1344, 'source_height': 760}
  assert calibration({}, frame)['height_m'] == 1.4
  events['liveCalibration']['calStatus'] = 'invalid'
  assert calibration({}, frame) is None
  events['liveCalibration']['calStatus'] = 'calibrated'
  events['deviceState']['deviceType'] = 'tici'
  assert calibration({}, frame) is None


def test_overlay_draws_production_projection_and_does_not_mask_vehicle_alerts(tmp_path, monkeypatch):
  import cluster_renderer as renderer_module
  import cluster_yolo_overlay as overlay_module
  from cluster_models import SimulatorInput
  from cluster_simulator import ClusterSimulator
  from cluster_scene import build_cluster_scene
  from dataclasses import replace
  from unittest.mock import create_autospec
  path = tmp_path/'objects'
  write_result(path, result())
  monkeypatch.setattr(overlay_module.time, 'monotonic', lambda: 10.2)
  overlay = ObjectOverlay(path)
  renderer = object.__new__(renderer_module.ClusterUiRenderer)
  renderer.width, renderer.height, renderer.screen_mode = 1920, 462, 7
  renderer._yolo_overlay = overlay
  from cluster_henry_layout import HenryLayout
  monkeypatch.delenv('CARROT_HUD_LAYOUT', raising=False)
  renderer._henry_layout = HenryLayout()
  state = replace(ClusterSimulator().update(SimulatorInput(), .05), onroad=True, camera_view_mode=0)
  scene = build_cluster_scene(state)
  for name in ('begin_scissor_mode', 'end_scissor_mode', 'draw_line_ex', 'draw_circle_v', 'draw_circle_lines'):
    monkeypatch.setattr(renderer_module.rl, name, lambda *a: None)
  draw = create_autospec(renderer._draw_text_with_stroke)
  renderer._draw_text_with_stroke = draw
  overlay.draw_world(renderer, scene, state)
  assert not overlay.error
  assert draw.call_args.args[0] == 'MOTO ~11m'
  calls = []
  renderer._render_world = lambda *a: calls.append('world')
  renderer._draw_hud = lambda *a: calls.append('hud')
  renderer._draw_alert_overlay = lambda *a: calls.append('alert')
  renderer._profile_start = lambda: 0
  renderer._profile_add = lambda *a: None
  renderer._font = renderer._korean_font = None
  overlay.draw_status = lambda *a: calls.append('yolo')
  import openpilot.common.indicator_display as indicator
  monkeypatch.setattr(indicator, 'draw', lambda *a: None)
  renderer.render(state, (False, False))
  assert calls == ['world', 'hud', 'yolo', 'alert']


def test_camera_overlay_rejects_wrong_stream_and_frame(tmp_path, monkeypatch):
  import cluster_renderer as renderer_module
  import cluster_yolo_overlay as overlay_module
  from cluster_config import CLUSTER_CAMERA_VIEW_MODE_ROAD_CAMERA
  path = tmp_path/'objects'
  write_result(path, result())
  monkeypatch.setattr(overlay_module.time, 'monotonic', lambda: 10.2)
  overlay = ObjectOverlay(path)
  renderer = NS(_camera_overlay_content_rect=lambda: NS(x=0,y=0,width=1280,height=462),
                _camera_overlay_wide=True)
  state = NS(onroad=True, camera_view_mode=CLUSTER_CAMERA_VIEW_MODE_ROAD_CAMERA)
  monkeypatch.setattr(renderer_module.rl, 'begin_scissor_mode', lambda *a: pytest.fail('Wrong camera painted'))
  overlay.draw_world(renderer, None, state)
  renderer._camera_overlay_wide = False
  renderer._live_road_camera = NS(display_frame=(25, 10.1, 1344, 760, False))
  overlay.draw_world(renderer, None, state)
  assert not overlay.error


def test_actual_cereal_calibration_validity_and_source_timestamp():
  from openpilot.cereal import log
  p = packet()
  p.update(events={}, valid={}, alive={}, mono={})
  fields = {'liveCalibration': {'calStatus': 'calibrated', 'rpyCalib': [.01, -.02, .03], 'height': [1.4]},
            'deviceState': {'deviceType': 'mici'}, 'roadCameraState': {'sensor': 'os04c10'}}
  for name, values in fields.items():
    event = log.Event.new_message(valid=True, logMonoTime=100_000_000_000, **{name: values})
    p['events'][name] = base64.b64encode(event.to_bytes()).decode()
    p['valid'][name] = p['alive'][name] = True
    p['mono'][name] = event.logMonoTime
  frame = {'source_width': 1344, 'source_height': 760}
  assert calibration(p, frame)['height_m'] == pytest.approx(1.4)
  p['valid']['liveCalibration'] = False
  assert calibration(p, frame) is None
  p['valid']['liveCalibration'] = True
  p['mono']['liveCalibration'] = 90_000_000_000
  assert calibration(p, frame) is None


@pytest.mark.parametrize('clock', ['monotonic', 'epoch'])
def test_real_model_live_packet_and_disconnect(tmp_path, clock):
  """Optional real-ONNX end-to-end test, enabled by YOLO_TEST_MODEL and YOLO_TEST_IMAGE."""
  import hashlib
  import os
  import subprocess
  import time
  model, image = os.environ.get('YOLO_TEST_MODEL'), os.environ.get('YOLO_TEST_IMAGE')
  if not model or not image:
    pytest.skip('Set YOLO_TEST_MODEL and YOLO_TEST_IMAGE for actual inference')
  source, output = tmp_path/'snapshot', tmp_path/'objects'
  buffer = BytesIO()
  Image.open(image).convert('RGB').resize((384, 240)).save(buffer, format='JPEG')
  p = packet()
  p['cameras']['road']['jpeg'] = base64.b64encode(buffer.getvalue()).decode()
  sha = hashlib.sha256(Path(model).read_bytes()).hexdigest()
  process = subprocess.Popen([sys.executable, str(ROOT/'tools/jetlink/hud_yolo.py'), 'live',
                              '--model', model, '--sha256', sha, '--snapshot', str(source),
                              '--output', str(output), '--seconds', '8', '--packet-clock', clock],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  seen = None
  try:
    for frame_id in range(60):
      now = time.monotonic()
      p['sent'] = now
      p['cameras']['road'].update(frame=frame_id, time=now, capture_time=now)
      temporary = source.with_suffix('.tmp')
      temporary.write_bytes(struct.pack('<d', time.time() if clock == 'epoch' else now)+json.dumps(p).encode())
      temporary.replace(source)
      time.sleep(.05)
      if output.exists():
        seen = valid_result(json.loads(output.read_text()), time.monotonic())
        if seen and seen['objects']:
          break
    assert seen and {'person', 'bus'} <= {o['name'] for o in seen['objects']}
    assert not seen['calibrated']  # No calibration supplied to this synthetic transport.
    source.unlink()
    time.sleep(.85)
    assert ObjectOverlay(output).read() is None
  finally:
    process.send_signal(2)
    stdout, stderr = process.communicate(timeout=10)
  assert process.returncode == 0, stderr.decode()
  assert json.loads(output.read_text())['status'] == 'stopped'
