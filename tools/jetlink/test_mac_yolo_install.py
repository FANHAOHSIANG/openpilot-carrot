import ast
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace as NS

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from yolo import install_mac_yolo as installer
from yolo.transport import HEADER, read_packet

SOURCE = '''def world_to_screen_label_anchor(*args):
    return None

class ClusterUiRenderer:
    def __init__(self):
        self.navigation = "keep the user's local NAV patch"
    def render(self, state):
        self._draw_hud(state)
        self._draw_alert_overlay(getattr(state, "alert", None))
    def _render_world(self, state):
        scene = self._scene_for_state(state)
        self._draw_scene(scene, state)
    def _camera_overlay_content_rect(self): pass
    def _world_view_shift_x(self, state): pass
    def _driving_panel_offset_design_x(self): pass
    def _camera_overlay_projection(self, state): pass
    def _draw_text_with_stroke(self, *args): pass
'''


def fake_install(tmp_path, monkeypatch):
  root = tmp_path/'CarrotMacHUD/carrot'
  renderer = root/installer.CLUSTER/'cluster_renderer.py'
  renderer.parent.mkdir(parents=True)
  renderer.write_text(SOURCE)
  (root/'tools/jetlink').mkdir(parents=True)
  (root/'tools/jetlink/hud_runtime.py').touch()
  app = root.parent/'jetlink/macos/build/Jetlink.app/Contents/MacOS/Jetlink'
  app.parent.mkdir(parents=True)
  app.touch()
  runtime = tmp_path/'CarrotHUD-YOLO'
  monkeypatch.setattr(installer, 'assert_stopped', lambda *a: None)
  monkeypatch.setattr(installer, 'fetch', lambda revision, path: (ROOT/path).read_bytes())
  calls = []
  monkeypatch.setattr(installer.subprocess, 'run', lambda args, **kw: calls.append(args))
  return NS(root=root, runtime=runtime, revision='1'*40), renderer, calls


def test_existing_mac_navigation_code_is_preserved_and_patch_is_idempotent():
  result = installer.patch_renderer(SOURCE)
  assert installer.patch_renderer(result) == result
  assert "keep the user's local NAV patch" in result
  assert result.index('self._yolo_overlay.draw_status') < result.index('self._draw_alert_overlay')
  ast.parse(result)
  assert result.count('ObjectOverlay.from_environment()') == 1
  with pytest.raises(ValueError):
    installer.patch_renderer(SOURCE.replace('_camera_overlay_projection', '_unsupported_interface'))


def test_real_pinned_mac_renderer_patch_when_fixture_is_available():
  fixture = os.environ.get('YOLO_TEST_MAC_RENDERER')
  if not fixture:
    pytest.skip('Set YOLO_TEST_MAC_RENDERER to the pinned a564ce1d Mac renderer')
  original = Path(fixture).read_text()
  patched = installer.patch_renderer(original)
  assert installer.patch_renderer(patched) == patched
  assert len(patched.splitlines()) == len(original.splitlines()) + 6
  compile(patched, 'mac-cluster-renderer.py', 'exec')


def test_install_and_hash_guarded_restore_without_branch_changes(tmp_path, monkeypatch):
  args, renderer, calls = fake_install(tmp_path, monkeypatch)
  installer.install(args)
  assert '_yolo_overlay' in renderer.read_text()
  assert all('git' not in call for call in calls)
  assert (args.runtime/'Start-YOLO.command').is_file()
  overlay = renderer.with_name('cluster_yolo_overlay.py')
  assert overlay.is_file()
  installer.restore(args.runtime/'config.json')
  assert renderer.read_text() == SOURCE and not overlay.exists()
  assert json.loads((args.runtime/'config.json').read_text())['installed'] is False


def test_restore_refuses_to_overwrite_later_user_changes(tmp_path, monkeypatch):
  args, renderer, _ = fake_install(tmp_path, monkeypatch)
  installer.install(args)
  changed = renderer.read_text() + '\n# new user change\n'
  renderer.write_text(changed)
  with pytest.raises(ValueError, match='安裝後檔案又被修改'):
    installer.restore(args.runtime/'config.json')
  assert renderer.read_text() == changed


def test_model_setup_does_not_overwrite_concurrent_hud_edit(tmp_path, monkeypatch):
  args, renderer, _ = fake_install(tmp_path, monkeypatch)
  monkeypatch.setattr(installer.subprocess, 'run', lambda *a, **kw: renderer.write_text(SOURCE+'\n# concurrent edit\n'))
  with pytest.raises(ValueError, match='準備期間 HUD 檔案已改變'):
    installer.install(args)
  assert renderer.read_text() == SOURCE+'\n# concurrent edit\n'
  assert not (args.runtime/'config.json').exists()


def test_bad_download_never_replaces_mac_hud(tmp_path, monkeypatch):
  args, renderer, _ = fake_install(tmp_path, monkeypatch)
  def fetch(revision, path):
    data = (ROOT/path).read_bytes()
    return data+b'corrupted' if path.endswith('core.py') else data
  monkeypatch.setattr(installer, 'fetch', fetch)
  with pytest.raises(ValueError, match='檔案雜湊不符'):
    installer.install(args)
  assert renderer.read_text() == SOURCE


@pytest.mark.parametrize('age,valid', [(.1, True), (.499, True), (.5, False), (5., False), (-1., False)])
def test_mac_epoch_clock_adapter_and_expiry(tmp_path, age, valid):
  path = tmp_path/'snapshot.packet'
  path.write_bytes(HEADER.pack(1000.-age) + json.dumps({'version': 1, 'sent': 100.}).encode())
  value = read_packet(path, 20., epoch_now=1000.)
  assert (value is not None) == valid
  if valid:
    assert value[0] == pytest.approx(20.-age)


def test_running_app_is_not_modified(monkeypatch, tmp_path):
  monkeypatch.setattr(installer.subprocess, 'check_output', lambda *a, **kw: '/Applications/Jetlink.app/Contents/MacOS/Jetlink\n')
  with pytest.raises(RuntimeError, match='退出 Jetlink'):
    installer.assert_stopped(tmp_path/'carrot', tmp_path/'runtime')


def test_stopping_trial_leaves_jetlink_app_running(tmp_path, monkeypatch):
  import signal
  sys.path.insert(0, str(ROOT/'tools/jetlink/yolo'))
  import mac_launcher as launcher
  config = tmp_path/'config.json'
  config.write_text(json.dumps({'installed': True, 'root': str(tmp_path/'carrot'),
                                'source': str(tmp_path/'source'), 'app': '/test/Jetlink', 'changes': []}))
  (tmp_path/'model').mkdir()
  (tmp_path/'model/manifest.json').write_text(json.dumps({'onnx_sha256': '0'*64}))
  monkeypatch.setattr(launcher, 'assert_stopped', lambda *a: None)
  monkeypatch.setattr(launcher.runpy, 'run_path', lambda *a: {'PACKET': tmp_path/'snapshot.packet'})
  events, starts = [], []
  worker = NS(poll=lambda: None, send_signal=lambda sig: events.append(('worker', sig)), wait=lambda **kw: 0,
              terminate=lambda: pytest.fail('Normal shutdown should use SIGINT'))
  def app_wait(**kwargs):
    raise KeyboardInterrupt
  app = NS(poll=lambda: None, wait=app_wait, terminate=lambda: pytest.fail('Jetlink stopped'))
  processes = iter((worker, app))
  def popen(args, **kwargs):
    starts.append((args, kwargs))
    return next(processes)
  monkeypatch.setattr(launcher.subprocess, 'Popen', popen)
  monkeypatch.setattr(sys, 'argv', ['mac_launcher.py', str(config)])
  assert launcher.main() == 0
  assert events == [('worker', signal.SIGINT)]
  assert all(k['start_new_session'] for _, k in starts)
  assert starts[0][1]['env']['CARROT_HUD_YOLO_FILE'] == starts[1][1]['env']['CARROT_HUD_YOLO_FILE']
