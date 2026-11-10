import ast
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import ModuleType, SimpleNamespace

import pytest

from openpilot.tools.clearance_shadow import auto_capture as auto
from openpilot.tools.clearance_shadow.capture_segment import verify_archive


GIB = 1024 ** 3
ROUTE_A = '00000384--8d2511ca94'
ROUTE_B = '00000385--8d2511ca95'


@pytest.fixture(autouse=True)
def plenty_of_space(monkeypatch):
  monkeypatch.setattr(auto.shutil, 'disk_usage', lambda _: SimpleNamespace(total=100 * GIB, free=80 * GIB))


@pytest.fixture
def folders(tmp_path):
  root, output = tmp_path / 'realdata', tmp_path / 'truck-shadow-auto'
  root.mkdir()
  output.mkdir()
  return root, output


def segment(root, route=ROUTE_A, number=0, *, camera=True, locked=False):
  path = root / f'{route}--{number}'
  path.mkdir()
  (path / 'rlog.zst').write_bytes(b'log' + bytes([number]))
  if camera:
    (path / 'fcamera.hevc').write_bytes(b'video' + bytes([number]))
  if locked:
    (path / 'rlog.lock').touch()
  return path


def blank_state():
  return {'version': 1, 'pending_routes': [], 'completed_routes': []}


def test_current_trip_is_packaged_once_per_segment(folders):
  root, output = folders
  a, b = segment(root, number=0), segment(root, number=1)
  segment(root, ROUTE_B, 0)
  state = blank_state()
  result = auto.process_once(root, output, state, ROUTE_A, lambda: True)
  assert set(result['saved_this_pass']) == {a.name + '.zip', b.name + '.zip'}
  assert state['pending_routes'] == [] and state['completed_routes'] == [ROUTE_A]
  assert verify_archive(output / (a.name + '.zip'))['segment'] == a.name
  assert verify_archive(output / (b.name + '.zip'))['segment'] == b.name
  first_mtime = (output / (a.name + '.zip')).stat().st_mtime_ns
  result = auto.process_once(root, output, state, ROUTE_A, lambda: True)
  assert result['saved_this_pass'] == []
  assert (output / (a.name + '.zip')).stat().st_mtime_ns == first_mtime
  assert not (output / (ROUTE_B + '--0.zip')).exists()


def test_restart_resumes_pending_and_falls_back_to_recent_route(folders):
  root, output = folders
  old, new = segment(root, ROUTE_A), segment(root, ROUTE_B)
  os.utime(old, ns=(1_000_000_000, 1_000_000_000))
  os.utime(new, ns=(2_000_000_000, 2_000_000_000))
  state = blank_state()
  state['pending_routes'] = [ROUTE_A]
  auto.write_json_atomic(output / 'state.json', state)
  state = auto.load_state(output / 'state.json')
  result = auto.process_once(root, output, state, None, lambda: True)
  assert result['latest_route'] == ROUTE_B
  assert set(result['saved_this_pass']) == {old.name + '.zip', new.name + '.zip'}
  assert state['pending_routes'] == []


def test_first_boot_does_not_archive_all_older_routes(folders):
  root, output = folders
  old, new = segment(root, ROUTE_A), segment(root, ROUTE_B)
  os.utime(old, ns=(1_000_000_000, 1_000_000_000))
  os.utime(new, ns=(2_000_000_000, 2_000_000_000))
  auto.process_once(root, output, blank_state(), None, lambda: True)
  assert (output / (new.name + '.zip')).is_file()
  assert not (output / (old.name + '.zip')).exists()


def test_locked_segment_waits_and_retries(folders):
  root, output = folders
  path = segment(root, locked=True)
  state = blank_state()
  result = auto.process_once(root, output, state, ROUTE_A, lambda: True)
  assert result['state'] == 'blocked' and result['blocked'][0]['reason'] == 'recording_locked'
  assert state['pending_routes'] == [ROUTE_A]
  assert not (output / (path.name + '.zip')).exists()
  (path / 'rlog.lock').unlink()
  result = auto.process_once(root, output, state, ROUTE_A, lambda: True)
  assert result['state'] == 'ready' and (output / (path.name + '.zip')).is_file()


def test_missing_video_is_reported_and_never_fabricated(folders):
  root, output = folders
  path = segment(root, camera=False)
  state = blank_state()
  result = auto.process_once(root, output, state, ROUTE_A, lambda: True)
  assert result['blocked'][0]['reason'] == 'missing_source'
  assert result['blocked'][0]['files'] == ['fcamera.hevc']
  assert state['pending_routes'] == [ROUTE_A]
  assert not (output / (path.name + '.zip')).exists()
  (path / 'fcamera.hevc').write_bytes(b'late camera data')
  assert auto.process_once(root, output, state, ROUTE_A, lambda: True)['state'] == 'ready'


def test_pending_missing_route_does_not_prevent_new_trip(folders):
  root, output = folders
  segment(root, ROUTE_A, camera=False)
  new = segment(root, ROUTE_B)
  state = blank_state()
  state['pending_routes'] = [ROUTE_A]
  result = auto.process_once(root, output, state, ROUTE_B, lambda: True)
  assert result['state'] == 'blocked'
  assert (output / (new.name + '.zip')).is_file()
  assert state['pending_routes'] == [ROUTE_A] and ROUTE_B in state['completed_routes']


def test_interrupt_leaves_pending_and_retry_completes(folders, monkeypatch):
  root, output = folders
  path = segment(root)
  state = blank_state()
  original = auto.pack_segment
  monkeypatch.setattr(auto, 'pack_segment', lambda *args: (_ for _ in ()).throw(KeyboardInterrupt()))
  with pytest.raises(KeyboardInterrupt):
    auto.process_once(root, output, state, ROUTE_A, lambda: True)
  assert auto.load_state(output / 'state.json')['pending_routes'] == [ROUTE_A]
  monkeypatch.setattr(auto, 'pack_segment', original)
  state = auto.load_state(output / 'state.json')
  auto.process_once(root, output, state, None, lambda: True)
  assert verify_archive(output / (path.name + '.zip'))['segment'] == path.name


@pytest.mark.parametrize('stop_signal', [signal.SIGINT, signal.SIGKILL])
def test_process_interruption_recovers_without_publishing_partial(folders, stop_signal):
  root, output = folders
  path = segment(root)
  marker = output / 'copying.marker'
  script = '''
import sys, time
from pathlib import Path
from types import SimpleNamespace
from openpilot.tools.clearance_shadow import auto_capture as auto
root, output, route = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
auto.shutil.disk_usage = lambda _: SimpleNamespace(total=100*1024**3, free=80*1024**3)
calls = [0]
def gate():
  calls[0] += 1
  if calls[0] == 5:
    (output / 'copying.marker').write_text('copy started')
    time.sleep(30)
  return True
with auto.worker_lock(output):
  auto.process_once(root, output, {'version': 1, 'pending_routes': [], 'completed_routes': []}, route, gate)
'''
  repo = Path(__file__).resolve().parents[4]
  child = subprocess.Popen([sys.executable, '-c', script, str(root), str(output), ROUTE_A], cwd=repo,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
  try:
    deadline = time.monotonic() + 10
    while not marker.exists() and child.poll() is None and time.monotonic() < deadline:
      time.sleep(0.02)
    assert marker.exists(), 'child did not begin copying'
    child.send_signal(stop_signal)
    child.wait(timeout=5)
    assert not (output / (path.name + '.zip')).exists()
    assert auto.load_state(output / 'state.json')['pending_routes'] == [ROUTE_A]
    if stop_signal == signal.SIGKILL:
      assert list(output.glob('*.part'))
    with auto.worker_lock(output):
      auto.clean_interrupted_parts(output, lambda: True)
      state = auto.load_state(output / 'state.json')
      auto.process_once(root, output, state, None, lambda: True)
    assert not list(output.glob('*.part'))
    assert verify_archive(output / (path.name + '.zip'))['segment'] == path.name
  finally:
    if child.poll() is None:
      child.kill()
      child.wait(timeout=5)


def test_cleanup_only_deletes_own_incomplete_parts(folders):
  _, output = folders
  part = output / ('.truck-auto-' + ROUTE_A + '--0.' + 'a' * 32 + '.part')
  part.write_bytes(b'incomplete')
  other = output / '.someone-else.part'
  other.write_bytes(b'keep')
  auto.clean_interrupted_parts(output, lambda: True)
  assert not part.exists() and other.read_bytes() == b'keep'


def test_offroad_lost_stops_without_publishing_partial(folders):
  root, output = folders
  path = segment(root)
  state = blank_state()
  count = 0

  def gate():
    nonlocal count
    count += 1
    return count < 6

  assert auto.process_once(root, output, state, ROUTE_A, gate)['state'] == 'offroad_not_confirmed'
  assert not (output / (path.name + '.zip')).exists()
  assert not list(output.glob('*.part'))
  assert state['pending_routes'] == [ROUTE_A]


def test_low_space_and_quota_stop_without_deleting_existing_files(folders, monkeypatch):
  root, output = folders
  path = segment(root)
  unrelated = output / 'user-data.txt'
  unrelated.write_text('keep')
  state = blank_state()
  monkeypatch.setattr(auto.shutil, 'disk_usage', lambda _: SimpleNamespace(total=100 * GIB, free=30 * GIB))
  result = auto.process_once(root, output, state, ROUTE_A, lambda: True)
  assert result['blocked'][0]['reason'] == 'free_space_reserve'
  assert unrelated.read_text() == 'keep' and not (output / (path.name + '.zip')).exists()
  monkeypatch.setattr(auto.shutil, 'disk_usage', lambda _: SimpleNamespace(total=100 * GIB, free=80 * GIB))
  result = auto.process_once(root, output, state, ROUTE_A, lambda: True, quota_bytes=1)
  assert result['blocked'][0]['reason'] == 'archive_quota'
  assert unrelated.read_text() == 'keep'


def test_invalid_existing_archive_is_not_overwritten(folders):
  root, output = folders
  path = segment(root)
  existing = output / (path.name + '.zip')
  existing.write_bytes(b'keep this broken zip for manual inspection')
  result = auto.process_once(root, output, blank_state(), ROUTE_A, lambda: True)
  assert result['state'] == 'blocked'
  assert 'invalid' in result['blocked'][0]['reason']
  assert existing.read_bytes() == b'keep this broken zip for manual inspection'


def test_invalid_state_is_retained_instead_of_replaced(folders):
  _, output = folders
  state_path = output / 'state.json'
  state_path.write_text('{broken')
  with pytest.raises(ValueError):
    auto.load_state(state_path)
  assert state_path.read_text() == '{broken'


class FakeParams:
  def __init__(self):
    self.values = {'IsOffroad': True, 'IsOnroad': False, 'DoShutdown': False, 'DoReboot': False, 'DoUninstall': False}

  def get_bool(self, name):
    return self.values.get(name, False)


class FakeSM:
  def __init__(self):
    self.healthy = True
    self.seen = {'deviceState': True, 'pandaStates': True}
    self.values = {'deviceState': SimpleNamespace(started=False, thermalStatus='green'),
                   'pandaStates': [SimpleNamespace(pandaType='known', ignitionLine=False, ignitionCan=False)]}

  def update(self, timeout):
    assert timeout == 0

  def all_alive(self, services):
    return self.healthy and services == ['deviceState', 'pandaStates']

  def all_valid(self, services):
    return self.healthy and services == ['deviceState', 'pandaStates']

  def __getitem__(self, name):
    return self.values[name]


def test_live_gate_requires_fresh_offroad_and_known_ignition_off():
  params, sm = FakeParams(), FakeSM()
  gate = auto.LiveOffroadGate(params, sm, 'unknown')
  assert gate()
  sm.healthy = False
  assert not gate()
  sm.healthy = True
  sm.seen['pandaStates'] = False
  assert not gate()
  sm.seen['pandaStates'] = True
  sm.values['deviceState'].started = True
  assert not gate()
  sm.values['deviceState'].started = False
  sm.values['deviceState'].thermalStatus = 'red'
  assert not gate()
  sm.values['deviceState'].thermalStatus = 'yellow'
  assert gate()
  sm.values['deviceState'].thermalStatus = 'green'
  sm.values['pandaStates'][0].ignitionCan = True
  assert not gate()
  sm.values['pandaStates'][0].ignitionCan = False
  sm.values['pandaStates'][0].ignitionLine = True
  assert not gate()
  sm.values['pandaStates'][0].ignitionLine = False
  sm.values['pandaStates'][0].pandaType = 'unknown'
  assert not gate()
  sm.values['pandaStates'][0].pandaType = 'known'
  params.values['IsOnroad'] = True
  assert not gate()
  params.values['IsOnroad'] = False
  params.values['DoShutdown'] = True
  assert not gate()


def test_state_reports_current_camera_setting_and_archived_segments(folders):
  root, output = folders
  path = segment(root)
  state = blank_state()
  auto.process_once(root, output, state, ROUTE_A, lambda: True, road_camera_setting=1)
  auto.process_once(root, output, state, ROUTE_A, lambda: True, road_camera_setting=1)
  status = json.loads((output / 'status.json').read_text())
  assert status['record_road_cam_current'] == 1
  assert status['latest_route_archives'] == [path.name + '.zip']


def test_existing_archive_winning_publication_race_is_not_overwritten(folders, monkeypatch):
  root, output = folders
  path = segment(root)
  final = output / (path.name + '.zip')
  real_link = auto.os.link

  def link_with_race(src, dst, **kwargs):
    final.write_bytes(b'preserve external file')
    real_link(src, dst, **kwargs)

  monkeypatch.setattr(auto.os, 'link', link_with_race)
  with pytest.raises(FileExistsError):
    auto.publish_segment(root, path, output, lambda: True)
  assert final.read_bytes() == b'preserve external file'
  assert not list(output.glob('*.part'))


def test_file_sync_failure_never_publishes_archive(folders, monkeypatch):
  root, output = folders
  path = segment(root)
  monkeypatch.setattr(auto.os, 'fsync', lambda _: (_ for _ in ()).throw(OSError('simulated power loss')))
  with pytest.raises(OSError, match='simulated power loss'):
    auto.publish_segment(root, path, output, lambda: True)
  assert not (output / (path.name + '.zip')).exists()
  assert not list(output.glob('*.part'))


def test_only_one_worker_owns_the_archive_directory(folders):
  _, output = folders
  with auto.worker_lock(output):
    with pytest.raises(BlockingIOError), auto.worker_lock(output):
      pass


def test_offroad_stability_restarts_after_an_invalid_sample():
  t = [0.0]
  auto.wait_for_stable_offroad(lambda: t[0] >= 1 and not 1.5 <= t[0] < 2,
                               seconds=2, clock=lambda: t[0], pause=lambda delay: t.__setitem__(0, t[0] + delay))
  assert t[0] >= 4


def test_manager_starts_worker_only_offroad_on_tici_with_spawn():
  root = Path(__file__).resolve().parents[3]
  tree = ast.parse((root / 'system/manager/process_config.py').read_text())
  calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
           and node.func.id == 'PythonProcess' and node.args and isinstance(node.args[0], ast.Constant)
           and node.args[0].value == 'truck_autopack']
  assert len(calls) == 1
  call = calls[0]
  assert call.args[1].value == 'openpilot.tools.clearance_shadow.auto_capture'
  assert isinstance(call.args[2], ast.Name) and call.args[2].id == 'only_offroad'
  options = {item.arg: item.value for item in call.keywords}
  assert isinstance(options['enabled'], ast.Name) and options['enabled'].id == 'TICI'
  assert isinstance(options['spawn'], ast.Constant) and options['spawn'].value is True


def test_real_manager_config_constructs_an_offroad_only_process(monkeypatch):
  import sys

  class ProcessStub:
    def __init__(self, *args, **kwargs):
      self.name, self.args, self.options = args[0], args, kwargs

  cereal = ModuleType('openpilot.cereal')
  cereal.car = SimpleNamespace(CarParams=object)
  params = ModuleType('openpilot.common.params')
  params.Params = object
  hardware = ModuleType('openpilot.system.hardware')
  hardware.PC, hardware.TICI = False, True
  process = ModuleType('openpilot.system.manager.process')
  process.PythonProcess = process.NativeProcess = process.DaemonProcess = ProcessStub
  for mod in (cereal, params, hardware, process):
    monkeypatch.setitem(sys.modules, mod.__name__, mod)
  monkeypatch.setattr(importlib.util, 'find_spec', lambda *_args: None)
  config = Path(__file__).resolve().parents[3] / 'system/manager/process_config.py'
  spec = importlib.util.spec_from_file_location('test_truck_manager_config', config)
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  worker = module.managed_processes['truck_autopack']
  assert worker.args[2](False, None, None) is True
  assert worker.args[2](True, None, None) is False
  assert worker.options['enabled'] is True and worker.options['spawn'] is True


def test_empty_log_root_never_creates_an_archive(folders):
  root, output = folders
  status = auto.process_once(root, output, blank_state(), None, lambda: True)
  assert status['latest_route'] is None and not list(output.glob('*.zip'))
  assert json.loads((output / 'status.json').read_text())['state'] == 'no_recordings'
