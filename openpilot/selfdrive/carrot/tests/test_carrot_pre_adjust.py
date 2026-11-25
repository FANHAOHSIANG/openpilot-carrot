import ast
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from openpilot.selfdrive.carrot.carrot_navi_cereal import build_carrot_navi_payload
from openpilot.selfdrive.carrot.carrot_navi_control import parse_carrot_navi_control
from openpilot.selfdrive.carrot.carrot_pre_adjust import pre_adjust_candidate, pre_adjust_payload


def snapshot(target=60, generated=10000, sent=10500, received=10_000_000_000):
  return {
    "connected": True, "session_id": "test",
    "items": {
      "speed": {"present": True, "sequence": 1, "sent_at_ms": sent,
                "received_mono_ns": received, "value": {
                  "road_limit_kph": 100,
                  "sdi": {"type": 1, "distance_m": 350, "speed_limit_kph": 50},
                  "pre_adjust": {"source": "amap_auto", "target_kph": target, "generated_at_ms": generated},
                }},
      "navigation_status": {"present": True, "value": {"guidance_active": True}},
    },
  }


def test_pipeline_preserves_road_limit_and_camera_and_expires_without_new_messages():
  s = snapshot()
  payload = build_carrot_navi_payload(s, publish_mono_ns=10_100_000_000)
  navi = parse_carrot_navi_control(payload)
  assert navi.speed.road_limit_kph == 100
  assert navi.speed.sdi_speed_limit_kph == 50
  assert navi.speed.sdi_distance_m == 350
  assert pre_adjust_candidate(navi, True, 10_100_000_000) == 250
  assert pre_adjust_candidate(navi, True, 11_500_000_000) == 250
  expired = build_carrot_navi_payload(s, publish_mono_ns=11_500_000_000)
  assert not expired["speed"]["preAdjustValid"]
  assert expired["speed"]["roadLimitKph"] == 100


@pytest.mark.parametrize("target", [None, True, False, "60", 60.0, 65, 0, -10, 210, float('nan')])
def test_invalid_target_cannot_control(target):
  assert pre_adjust_payload(snapshot(target)["items"]["speed"], 10_100_000_000) == (0, 0)


@pytest.mark.parametrize("generated,sent,received,now", [
  (11000, 10500, 10_000_000_000, 10_100_000_000),
  (8500, 10500, 10_000_000_000, 10_100_000_000),
  (0, 10500, 10_000_000_000, 10_100_000_000),
  (10000, 10500, 0, 10_100_000_000),
  (10000, 10500, 10_000_000_000, 9_000_000_000),
  (10000, True, 10_000_000_000, 10_100_000_000),
])
def test_bad_or_expired_time_fails_closed(generated, sent, received, now):
  assert pre_adjust_payload(snapshot(generated=generated, sent=sent, received=received)["items"]["speed"], now) == (0, 0)


def test_repeated_old_policy_does_not_gain_lifetime_from_other_speed_updates():
  first = pre_adjust_payload(snapshot()["items"]["speed"], 10_000_000_000)
  repeat = pre_adjust_payload(snapshot(sent=11000, received=10_500_000_000)["items"]["speed"], 10_500_000_000)
  assert first == repeat == (60, 11_500_000_000)
  assert pre_adjust_payload(snapshot(sent=12000, received=11_500_000_000)["items"]["speed"], 11_500_000_000) == (0, 0)


def test_stop_offroute_disconnect_master_off_and_absence_cancel():
  navi = parse_carrot_navi_control(build_carrot_navi_payload(snapshot(), 10_100_000_000))
  assert pre_adjust_candidate(navi, False, 10_100_000_000) == 250
  for case in (None, replace(navi, guidance_active=False), replace(navi, off_route=True),
               replace(navi, speed=replace(navi.speed, present=False))):
    assert pre_adjust_candidate(case, True, 10_100_000_000) == 250
  s = snapshot(); s["connected"] = False
  assert parse_carrot_navi_control(build_carrot_navi_payload(s, 10_100_000_000)) is None
  s = snapshot(); del s["items"]["speed"]["value"]["pre_adjust"]
  assert not build_carrot_navi_payload(s, 10_100_000_000)["speed"]["preAdjustValid"]
  s = snapshot(); s["items"]["speed"]["value"]["pre_adjust"]["source"] = "google"
  assert not build_carrot_navi_payload(s, 10_100_000_000)["speed"]["preAdjustValid"]


def select_with_production_code(navi, **values):
  """Execute the actual CarrotServ arbitration block, without hardware imports."""
  path = Path(__file__).parents[1] / 'carrot_serv.py'
  tree = ast.parse(path.read_text())
  cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'CarrotServ')
  method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'update_navi')
  def assigns(n, name):
    return isinstance(n, ast.Assign) and any(isinstance(v, ast.Name) and v.id == name for t in n.targets for v in ast.walk(t))
  start = next(i for i,n in enumerate(method.body) if assigns(n, 'speed_n_sources'))
  end = next(i for i,n in enumerate(method.body) if assigns(n, 'desired_speed'))
  block = ast.Module(body=method.body[start:end+1], type_ignores=[])
  env = dict(shared_pre_speed=250, pre_adjust_candidate=pre_adjust_candidate, math=__import__('math'),
             time=SimpleNamespace(monotonic_ns=lambda: 10_100_000_000),
             self=SimpleNamespace(carrot_navi_active=True, carrot_navi_control=navi,
                                  external_navigation_active=True, autoNaviSpeedCtrlMode=1,
                                  turnSpeedControlMode=0, autoCurveSpeedLowerLimit=30),
             atc_desired=250, atc_desired_next=250, sdi_speed=250, sdi_source='cam',
             vehicle_camera_speed=250, vehicle_bump_speed=250, vehicle_school_zone_speed=250,
             vehicle_section_zone_speed=250, limit_speed=100, route_speed=250, vturn_speed=250)
  env.update(values)
  exec(compile(ast.fix_missing_locations(block), str(path), 'exec'), env)
  return env['desired_speed'], env['source']


def test_actual_selection_never_overrides_lower_camera_turn_or_road_speed():
  navi = parse_carrot_navi_control(build_carrot_navi_payload(snapshot(), 10_100_000_000))
  assert select_with_production_code(navi) == (100, 'road')
  assert select_with_production_code(navi, sdi_speed=40) == (40, 'cam')
  assert select_with_production_code(navi, atc_desired=30) == (30, 'atc')
  assert select_with_production_code(navi, limit_speed=50) == (50, 'road')
  assert select_with_production_code(replace(navi, speed=replace(navi.speed, pre_adjust_kph=120))) == (100, 'road')
  assert select_with_production_code(None) == (100, 'road')


def test_actual_cereal_roundtrip():
  import capnp
  root = Path(__file__).parents[3] / 'cereal'
  schema = capnp.load(str(root / 'custom.capnp'), imports=[str(root)])
  message = schema.CarrotNaviState.new_message(**build_carrot_navi_payload(snapshot(), 10_100_000_000))
  with schema.CarrotNaviState.from_bytes(message.to_bytes()) as reader:
    navi = parse_carrot_navi_control(reader)
    assert navi.speed.road_limit_kph == 100
    assert pre_adjust_candidate(navi, True, 10_100_000_000) == 250
    assert pre_adjust_candidate(navi, True, 11_500_000_000) == 250


def test_full_service_publication_and_cached_item_expiry(monkeypatch):
  from openpilot.selfdrive.carrot import carrot_serv

  class Params:
    def __init__(self, *_args): pass
    def get(self, key):
      return str({'AutoNaviSpeedCtrlMode': 1, 'AutoNaviSpeedSafetyFactor': 100}.get(key, 0))
    def get_int(self, key): return int(self.get(key))
    def get_float(self, key): return float(self.get(key))
    def get_bool(self, key): return bool(self.get_int(key))

  monkeypatch.setattr(carrot_serv, 'Params', Params)
  monkeypatch.setattr(carrot_serv.time, 'monotonic_ns', lambda: 10_100_000_000)
  serv = carrot_serv.CarrotServ()
  monkeypatch.setattr(serv, '_update_gps', lambda *_: 0.)
  monkeypatch.setattr(serv, 'update_nav_instruction', lambda _: None)
  monkeypatch.setattr(serv, 'update_auto_turn', lambda *_: (250., 'none', 250., 0.))
  monkeypatch.setattr(serv, '_vehicle_navigation_display', lambda _: (False, 0, False))
  s = snapshot(); s['items']['speed']['value'].pop('sdi')

  class SubMaster(dict):
    alive = {'carrotNavi': True, 'carState': False, 'selfdriveState': False, 'navInstruction': False}
    valid = {'carrotNavi': True}
    updated = {'carrotNavi': True}

  sm = SubMaster(carrotNavi=build_carrot_navi_payload(s, 10_100_000_000),
                 modelV2=SimpleNamespace(meta=SimpleNamespace(modelTurnSpeed=16.)))
  sent = {}
  pm = SimpleNamespace(send=lambda name, message: sent.update({name: message}))
  serv.update_navi('', sm, pm, 250., [], [], 250., 'gpsLocationExternal')
  result = sent['carrotMan'].carrotMan
  assert (result.desiredSource, result.desiredSpeed, result.nRoadLimitSpeed) == ('road', 100, 100)
  sm.updated['carrotNavi'] = False
  monkeypatch.setattr(carrot_serv.time, 'monotonic_ns', lambda: 11_500_000_000)
  serv.update_navi('', sm, pm, 250., [], [], 250., 'gpsLocationExternal')
  result = sent['carrotMan'].carrotMan
  assert (result.desiredSource, result.desiredSpeed, result.nRoadLimitSpeed) == ('road', 100, 100)


@pytest.mark.parametrize("target", [30, 60, 100, 120])
def test_fresh_recomputed_unbound_native_advisory_is_quarantined(target):
  for i in range(20):
    now = 10_000_000_000 + i * 1_000_000_000
    s = snapshot(target=target, generated=10000+i*1000, sent=10000+i*1000, received=now)
    navi = parse_carrot_navi_control(build_carrot_navi_payload(s, now))
    assert navi.speed.pre_adjust_kph == target  # fresh received value remains observable
    assert pre_adjust_candidate(navi, True, now) == 250
    assert select_with_production_code(navi, sdi_speed=40) == (40, 'cam')
