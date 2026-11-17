from dataclasses import replace
from pathlib import Path
import pytest
import capnp
from openpilot.selfdrive.carrot.carrot_navi_cereal import build_carrot_navi_payload
from openpilot.selfdrive.carrot.carrot_navi_control import parse_carrot_navi_control
from openpilot.selfdrive.carrot.carrot_pre_adjust import shared_pre_adjust_candidate
from openpilot.selfdrive.carrot.tests.test_carrot_pre_adjust import snapshot, select_with_production_code

SOURCES = ("amap_auto", "amap_phone", "google_noo")
NOW = 10_100_000_000


def shared(source):
  s = snapshot()
  s["items"]["speed"]["value"].pop("pre_adjust")
  s["items"]["navigation_status"].update(sent_at_ms=10500, received_mono_ns=10_000_000_000)
  s["items"]["navigation_status"]["value"]["pre_adjust_control"] = {
    "source": source, "enabled": True, "generated_at_ms": 10000,
  }
  s["items"]["guidance_current"] = {
    "present": True, "sequence": 1, "sent_at_ms": 10500,
    "source_timestamp_ms": 10000, "received_mono_ns": 10_000_000_000,
    "value": {"turn_type": 13, "distance_m": 150},
  }
  return s


def parse(s):
  return parse_carrot_navi_control(build_carrot_navi_payload(s, NOW))


@pytest.mark.parametrize("source", SOURCES)
def test_real_schema_and_arbitration(source):
  root = Path(__file__).parents[3] / "cereal"
  schema = capnp.load(str(root / "custom.capnp"), imports=[str(root)])
  msg = schema.CarrotNaviState.new_message(**build_carrot_navi_payload(shared(source), NOW))
  with schema.CarrotNaviState.from_bytes(msg.to_bytes()) as reader:
    navi = parse_carrot_navi_control(reader)
    assert navi.shared_pre_adjust_source == source
    proposal = shared_pre_adjust_candidate(navi, True, NOW, 45)
    assert proposal == 45
    assert select_with_production_code(navi, shared_pre_speed=proposal) == (45, "pre")
    assert select_with_production_code(navi, shared_pre_speed=proposal, sdi_speed=30) == (30, "cam")
    assert navi.speed.road_limit_kph == 100
    assert shared_pre_adjust_candidate(navi, True, 11_500_000_000, 45) == 250


@pytest.mark.parametrize("source", SOURCES)
@pytest.mark.parametrize("case", ["off", "stop", "offroute", "stale_turn", "future_turn", "switch", "no_permission", "disconnect"])
def test_withdrawal(source, case):
  s = shared(source)
  status=s["items"]["navigation_status"]
  turn=s["items"]["guidance_current"]
  if case=="off": status["value"]["pre_adjust_control"]["enabled"]=False
  if case=="stop": status["value"]["guidance_active"]=False
  if case=="offroute": status["value"]["off_route"]=True
  if case=="stale_turn": turn["source_timestamp_ms"]=8000
  if case=="future_turn": turn["source_timestamp_ms"]=11000
  if case=="switch": turn["present"]=False
  if case=="no_permission": status["value"].pop("pre_adjust_control")
  if case=="disconnect": s["connected"]=False
  assert shared_pre_adjust_candidate(parse(s), True, NOW, 45)==250


@pytest.mark.parametrize("source", SOURCES)
def test_no_guessed_ramp_straight_or_arrival_and_master_off(source):
  navi=parse(shared(source))
  assert shared_pre_adjust_candidate(navi,False,NOW,45)==250
  for code in (-1, 51, 101, 102, 201):
    n=replace(navi,current=replace(navi.current,turn_type=code))
    assert shared_pre_adjust_candidate(n,True,NOW,45)==250
  for value in (float("nan"),float("inf"),0,250):
    assert shared_pre_adjust_candidate(navi,True,NOW,value)==250
  assert shared_pre_adjust_candidate(replace(navi,current=replace(navi.current,distance_m=0)),True,NOW,45)==250


from types import SimpleNamespace

@pytest.mark.parametrize('source', SOURCES)
def test_full_shared_service(monkeypatch, source):
  from openpilot.selfdrive.carrot import carrot_serv

  class Params:
    def __init__(self, *_args): pass
    def get(self, key):
      return str({'AutoNaviSpeedCtrlMode': 1, 'AutoNaviSpeedSafetyFactor': 100, 'AutoTurnControlSpeedTurn': 30}.get(key, 0))
    def get_int(self, key): return int(self.get(key))
    def get_float(self, key): return float(self.get(key))
    def get_bool(self, key): return bool(self.get_int(key))

  monkeypatch.setattr(carrot_serv, 'Params', Params)
  monkeypatch.setattr(carrot_serv.time, 'monotonic_ns', lambda: 10_100_000_000)
  serv = carrot_serv.CarrotServ()
  monkeypatch.setattr(serv, '_update_gps', lambda *_: 0.)
  monkeypatch.setattr(serv, 'update_nav_instruction', lambda _: None)
  monkeypatch.setattr(serv, 'update_auto_turn', lambda *_: (45., 'turn right', 30., 40.))
  monkeypatch.setattr(serv, '_vehicle_navigation_display', lambda _: (False, 0, False))
  s = shared(source); s['items']['speed']['value'].pop('sdi')

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
  assert (result.desiredSource, result.desiredSpeed, result.nRoadLimitSpeed) == ('pre', 45, 100)
  sm.updated['carrotNavi'] = False
  monkeypatch.setattr(carrot_serv.time, 'monotonic_ns', lambda: 11_500_000_000)
  serv.update_navi('', sm, pm, 250., [], [], 250., 'gpsLocationExternal')
  result = sent['carrotMan'].carrotMan
  assert (result.desiredSource, result.desiredSpeed, result.nRoadLimitSpeed) == ('road', 100, 100)
