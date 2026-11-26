from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cluster"))
import cluster_live


class SubMaster(dict):
  def __init__(self):
    super().__init__()
    self.recv_time = {}
    self.valid = {"navRoute": True, "carrotMan": True}
    self.alive = {"carrotMan": True}


def point(x, y):
  return SimpleNamespace(latitude=25. + x / 111133., longitude=121. + y / (111133. * math.cos(math.radians(25.))))


class Replay:
  def __init__(self, monkeypatch):
    self.source = object.__new__(cluster_live.OpenpilotLiveSource)
    self.source.sm = SubMaster()
    self.source._nav_route_coords = ()
    self.source._nav_route_id = 0
    self.now = 10.
    self.model = (cluster_live.ModelPathPoint(0., 0.), cluster_live.ModelPathPoint(40., 1.))
    self.state = replace(cluster_live.standby_state(), model_path=self.model)
    monkeypatch.setattr(cluster_live, "time", SimpleNamespace(monotonic=lambda: self.now))

  def route(self, points, route_id=1):
    self.source.sm["navRoute"] = SimpleNamespace(coordinates=[point(*p) for p in points], carrotRouteId=route_id)
    self.source._apply_service_update("navRoute", self.now)

  def fix(self, x=0., y=0., heading=0., **extra):
    pos = point(x, y)
    self.source.sm["carrotMan"] = SimpleNamespace(
      xPosLat=pos.latitude, xPosLon=pos.longitude, xPosAngle=heading, **extra,
    )
    self.source.sm.recv_time["carrotMan"] = self.now

  def hud(self):
    return self.source._with_external_nav_route(self.state)


def test_stale_invalid_and_cleared_input_preserve_model(monkeypatch):
  replay = Replay(monkeypatch)
  replay.route([(0., 0.), (30., 0.)])
  replay.fix(positionHeadingValid=False)
  assert replay.hud() is replay.state
  replay.fix(heading=math.nan)
  assert replay.hud() is replay.state
  replay.fix(positionFixMonoTime=int(7e9))
  assert replay.hud() is replay.state
  replay.fix(positionHeadingValid=True, positionFixMonoTime=int(10e9))
  assert replay.hud().model_path != replay.model
  replay.now += 1.01
  assert replay.hud() is replay.state
  replay.fix()
  assert replay.hud().model_path != replay.model
  replay.source.sm.valid["navRoute"] = False
  replay.route([(0., 0.), (30., 0.)])
  assert replay.hud() is replay.state
  replay.source.sm.valid["navRoute"] = True
  replay.route([(0., 0.), (30., 0.)])
  replay.now += 15.1
  replay.fix()
  assert replay.hud() is replay.state


def test_heartbeat_keeps_anchor_and_route_change_drops_old_path(monkeypatch):
  replay = Replay(monkeypatch)
  route = [(0., 0.), (20., 0.), (40., 6.)]
  replay.route(route)
  replay.fix()
  visible = replay.hud().model_path
  assert visible != replay.model
  replay.now += .1
  replay.route(route)
  replay.fix(y=25.)
  assert replay.hud().model_path == visible
  replay.now += .1
  replay.route([(0., 40.), (40., 40.)], route_id=2)
  replay.fix()
  assert replay.hud() is replay.state


def test_turn_keeps_order_and_stops_at_discontinuity(monkeypatch):
  replay = Replay(monkeypatch)
  replay.route([(0., 0.), (10., 0.), (22., 8.), (31., 18.), (38., 25.), (36., 40.), (53., 26.)])
  replay.fix(heading=359.)
  before = replay.hud()
  assert len(before.model_path) == 5
  replay.now += .2
  replay.fix(x=1., heading=2.)
  after = replay.hud()
  assert len(after.model_path) == 5
  assert after.model_path[-1].lateral_m > 20.
  assert all(a.forward_m < b.forward_m for a, b in zip(after.model_path, after.model_path[1:]))
  assert replay.state.model_path == replay.model
  replay.now += .1
  replay.route([(0., 0.), (16., 2.), (120., 2.), (140., 2.)], route_id=2)
  replay.fix()
  assert len(replay.hud().model_path) == 2


def test_wrong_way_and_untagged_far_route_preserve_model(monkeypatch):
  replay = Replay(monkeypatch)
  replay.route([(30., 0.), (0., 0.)])
  replay.fix()
  assert replay.hud() is replay.state
  replay.route([(0., 140.), (30., 140.)], route_id=2)
  replay.fix()
  assert replay.hud() is replay.state
