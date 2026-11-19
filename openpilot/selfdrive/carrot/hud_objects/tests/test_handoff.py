from pathlib import Path
from types import SimpleNamespace
import ast

import numpy as np
import pytest

from openpilot.selfdrive.carrot.cluster.hud_objects import HudObjectReader
from openpilot.selfdrive.carrot.hud_objects import transport
from openpilot.selfdrive.carrot.hud_objects.detectors import decode_traffic_output
from openpilot.selfdrive.carrot.hud_objects.worker import Output, wide_observation
from openpilot.tools.clearance_shadow.onnx_observer import decode_output


def test_wide_forward_has_separate_truck_policy_and_calibrated_hud_outputs(tmp_path):
  prediction = np.zeros((1, 14, 8400), dtype=np.float32)
  # A motorcycle in this wide frame is valid for the display only.
  prediction[0, :4, 0] = [306, 430, 80, 60]
  prediction[0, 4 + 6, 0] = .90
  transform = (1.0, 0, 0, 640, 640)
  assert decode_output(prediction, transform) == []
  path = tmp_path / 'truck.json'
  transport.write_snapshot(path, {'version': 1, 't': 20., 'camera': 'wideRoad',
                                  'objects': decode_traffic_output(prediction, transform)})
  shared = wide_observation(path, 20.1)
  assert [row[0] for row in shared['objects']] == ['motorcycle']
  hud_path = tmp_path / 'hud.json'
  Output(hud_path).write({'traffic': shared,
                         'cone': {'t': 20.2, 'camera': 'road', 'objects': [['cone', .55, .7, .06, .12, .9]]}}, 20.25)
  reader = HudObjectReader(hud_path)
  calibration = SimpleNamespace(calStatus='calibrated', rpyCalib=(0., 0., 0.),
                                wideFromDeviceEuler=(0., 0., 0.), height=(1.2,))
  def read(now):
    return [(o.kind, o.camera) for o in reader.read(now, 'mici', 'os04c10', calibration)]
  assert set(read(20.25)) == {('motorcycle', 'wideRoad'), ('cone', 'road')}
  assert read(21.05) == [('cone', 'road')]
  assert read(21.25) == []


def test_connection_predicate_requires_the_local_panel_and_opt_in():
  # Like the manager startup tests, exercise the platform predicate without loading the C4 hardware.
  path = Path(__file__).resolve().parents[4] / 'system/manager/process_config.py'
  defs = [n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)
          and n.name in ('cluster_hud_active', 'enable_c4_hud_objects')]
  ns = {'Params': object, 'car': SimpleNamespace(CarParams=object)}
  exec(compile(ast.Module(body=defs, type_ignores=[]), str(path), 'exec'), ns)
  values = {'ClusterHud': 1, 'C4HudObjects': True, 'C4HudUsbConnected': True, 'ClusterHudConnected': True}
  params = SimpleNamespace(get_bool=values.__getitem__, get_int=values.__getitem__)
  eligible = ns['enable_c4_hud_objects']
  assert eligible(True, params, None)
  assert not eligible(False, params, None)
  for key in ('C4HudObjects', 'ClusterHud', 'C4HudUsbConnected'):
    before = values[key]
    values[key] = 0
    assert not eligible(True, params, None)
    values[key] = before


def test_failed_write_preserves_last_complete_packet(tmp_path, monkeypatch):
  path = tmp_path / 'hud.json'
  transport.write_snapshot(path, {'t': 10.})
  first = path.read_bytes()
  def fail(*args):
    raise OSError('full tmpfs')
  monkeypatch.setattr(transport.os, 'replace', fail)
  with pytest.raises(OSError):
    transport.write_snapshot(path, {'t': 11.})
  assert path.read_bytes() == first
  assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize('stopped,expect_alert', [
  ({'c4_hud_objects'}, False), ({'modeld'}, True), ({'modeld', 'c4_hud_objects'}, True),
])
def test_display_worker_outage_only_exempts_the_display(stopped, expect_alert):
  # Read the production alert predicate without importing target-only dependencies.
  path = Path(__file__).resolve().parents[3] / 'selfdrived/selfdrived.py'
  cls = next(n for n in ast.parse(path.read_text()).body if isinstance(n, ast.ClassDef) and n.name == 'SelfdriveD')
  methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
  init = next(n for n in methods['__init__'].body if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Attribute) and t.attr == 'ignored_processes' for t in n.targets))
  alert = next(n for n in methods['update_events'].body if isinstance(n, ast.If)
               and any(isinstance(e, ast.Attribute) and e.attr == 'processNotRunning' for e in ast.walk(n.body[0])))
  state = SimpleNamespace(sm=SimpleNamespace(recv_frame={'managerState': 1}))
  ns = {'self': state, 'not_running': stopped, 'dm_fallback_processes': set()}
  exec(compile(ast.Module(body=[init], type_ignores=[]), str(path), 'exec'), ns)
  assert bool(eval(compile(ast.Expression(alert.test), str(path), 'eval'), ns)) == expect_alert
