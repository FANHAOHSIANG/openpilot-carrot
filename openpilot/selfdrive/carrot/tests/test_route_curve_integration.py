"""Execute complete production methods with real cereal messages, without IPC.

The AST loader omits platform/native imports only. It does not copy or rewrite
control logic. Device process startup and transport remain separate checks.
"""
import ast
import collections
import math
from pathlib import Path
from types import SimpleNamespace as NS
from typing import Any, Optional

import numpy as np
import pytest

from openpilot.cereal import car, log
from openpilot.common.constants import CV
from openpilot.common.filter_simple import MyMovingAverage
from openpilot.selfdrive.carrot.carrot_navi_control import CarrotNaviControl, parse_carrot_navi_control
from openpilot.selfdrive.carrot.gps_sources import GPSSources
from openpilot.selfdrive.carrot.route_curve import RouteCurveSpeed
from openpilot.selfdrive.carrot.osm_curve import OsmCurveClient, read_message
from openpilot.selfdrive.carrot.osmd import OsmWorker
from openpilot.selfdrive.carrot.osm_map import Road
from openpilot.selfdrive.carrot.tests.test_route_curve import lonlat, model_for, road
from openpilot.selfdrive.navigation.source import RouteSource


CARROT = Path(__file__).parents[1]


def new_message(name, valid=True):
  event = log.Event.new_message()
  event.init(name)
  event.valid = valid
  return event


def load_class(filename, name, env):
  tree = ast.parse((CARROT / filename).read_text())
  # Preserve the production class and literal constants needed by its methods.
  body = [n for n in tree.body if isinstance(n, ast.Assign) or (isinstance(n, ast.ClassDef) and n.name == name)]
  exec(compile(ast.Module(body=body, type_ignores=[]), str(CARROT / filename), 'exec'), env)
  return env[name]


@pytest.fixture
def pipeline(tmp_path):
  now = [10.]
  values = {'TurnSpeedControlMode': 2, 'MapTurnSpeedFactor': 100, 'AutoCurveSpeedLowerLimit': 30,
            'AutoNaviSpeedDecelRate': 100, 'AutoRoadSpeedLimitOffset': -1, 'IsMetric': 1, 'IsOnroad': 1}

  class Params:
    def __init__(self, *_args):
      pass

    def get(self, key):
      return str(values.get(key, 0))

    def get_int(self, key):
      return int(self.get(key))

    def get_float(self, key):
      return float(self.get(key))

    def get_bool(self, key):
      return bool(self.get_int(key))

  env = {'np': np, 'math': math, 'collections': collections, 'Params': Params, 'CV': CV, 'log': log,
             'time': NS(monotonic=lambda: now[0]), 'GPSSources': GPSSources, 'MyMovingAverage': MyMovingAverage,
             'CarrotNaviControl': CarrotNaviControl, 'parse_carrot_navi_control': parse_carrot_navi_control,
             'messaging': NS(new_message=new_message), 'RouteCurveSpeed': RouteCurveSpeed,
             'Any': Any, 'Dict': dict, 'List': list, 'Optional': Optional}
  serv_cls = load_class('carrot_serv.py', 'CarrotServ', env)
  # CarrotMan's module constants include hardware/config expressions; only its
  # unchanged complete method is needed to exercise the route calculation link.
  man_tree = ast.parse((CARROT / 'carrot_man.py').read_text())
  cls = next(n for n in man_tree.body if isinstance(n, ast.ClassDef) and n.name == 'CarrotMan')
  method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'carrot_navi_route')
  exec(compile(ast.Module(body=[method], type_ignores=[]), str(CARROT / 'carrot_man.py'), 'exec'), env)
  serv = serv_cls()
  cs = car.CarState.new_message(vEgo=25., vCluRatio=1.)
  gps = new_message('gpsLocation').gpsLocation
  gps.latitude, gps.longitude, gps.bearingDeg, gps.speed, gps.hasFix = 25., 121., 90., 25., True
  xy = road()

  class SM(dict):
    pass

  sm = SM(deviceState=log.DeviceState.new_message(), carState=cs, selfdriveState=NS(distanceTraveled=0), gpsLocation=gps,
          carrotNavi=new_message('carrotNavi').carrotNavi,
          navInstruction=new_message('navInstruction').navInstruction, modelV2=model_for(xy))
  sm.alive = sm.valid = {key: key not in ('carrotNavi', 'navInstruction') for key in sm}
  sm.updated = dict.fromkeys(sm, True)
  sm.logMonoTime = {'modelV2': int(now[0] * 1e9)}
  sm.recv_time = {'gpsLocation': now[0]}
  man = NS(osm_curve=OsmCurveClient(tmp_path / 'ipc'), params=Params(), carrot_serv=serv, sm=sm, route_curve_speed=RouteCurveSpeed(),
           navi_points=lonlat(xy), navi_points_active=True, nav_route_id=1, autoCurveSpeedFactor=1.)
  sent = {}
  pm = NS(send=lambda name, msg: sent.update({name: msg}))

  def update(vturn=250.):
    now[0] += .05
    sm.logMonoTime['modelV2'] = int(now[0] * 1e9)
    sm.recv_time['gpsLocation'] = now[0]
    coords, distances, speed = env['carrot_navi_route'](man)
    serv.update_navi('', sm, pm, vturn, coords, distances, speed, 'gpsLocation')
    return sent['carrotMan'].carrotMan

  update.man, update.serv, update.params, update.sm, update.now = man, serv, values, sm, now
  return update


def test_route_participates_without_tbt_and_keeps_visual_lower_cap(pipeline):
  for _ in range(12):
    result = pipeline()
  assert result.xTurnInfo == -1
  assert result.desiredSource == 'route'
  assert 70 < result.desiredSpeed < 90
  assert 'rc=matched:' in result.szPosRoadName
  assert result.naviPaths
  result = pipeline(45.)
  assert (result.desiredSource, result.desiredSpeed) == ('vturn', 45)


@pytest.mark.parametrize('mode', [0, 1])
def test_existing_modes_can_disable_route_candidate(pipeline, mode):
  pipeline.params['TurnSpeedControlMode'] = mode
  for _ in range(12):
    result = pipeline(150.)
  assert result.desiredSource != 'route'
  assert result.desiredSpeed == (200 if mode == 0 else 150)


def test_missing_route_and_half_factor_do_not_create_braking(pipeline):
  pipeline.man.navi_points = []
  pipeline.man.navi_points_active = False
  pipeline.params['MapTurnSpeedFactor'] = 50
  for _ in range(12):
    result = pipeline()
  assert result.desiredSource == 'road' and result.desiredSpeed == 200
  assert '/no_route:' in result.szPosRoadName


def test_external_without_geometry_never_borrows_saved_mapbox_route():
  source = RouteSource()
  source.mapbox = tuple(map(tuple, lonlat(road())[:, ::-1]))
  assert source.select(False)
  assert source.select(True) == []
  assert source.select(True, NS(route=NS(present=False, polyline=()), off_route=False)) is None
  assert source.selected == ('external', ())


def test_road_limit_still_wins_over_route(pipeline):
  for _ in range(12):
    pipeline()
  pipeline.params['AutoRoadSpeedLimitOffset'] = 0
  pipeline.serv.active_count = pipeline.serv.active_sdi_count = 80
  pipeline.serv.nRoadLimitSpeed = 40
  result = pipeline()
  assert (result.desiredSource, result.desiredSpeed) == ('road', 40)


def test_route_bend_is_not_hidden_by_distant_next_tbt(pipeline):
  pipeline.serv.active_count = pipeline.serv.active_sdi_count = 80
  pipeline.serv.xTurnInfo = 3
  pipeline.serv.xDistToTurn = 1200
  for _ in range(12):
    result = pipeline()
  assert result.xDistToTurn == 1200
  assert result.desiredSource == 'route'
  assert result.desiredSpeed < 90


def test_offroad_resets_old_speed_and_retains_route(pipeline):
  for _ in range(12):
    pipeline()
  assert pipeline.man.route_curve_speed.speed < 100
  pipeline.params['IsOnroad'] = 0
  result = pipeline()
  assert pipeline.man.route_curve_speed.speed == 250
  assert len(pipeline.man.navi_points) > 0
  assert result.desiredSource != 'route'


def test_osm_without_destination_through_full_control_pipeline(pipeline, tmp_path):
  pipeline.params['OsmCurveSpeedEnabled'] = 1
  pipeline.man.navi_points = []
  pipeline.man.navi_points_active = False
  worker = OsmWorker(tmp_path / 'maps', pipeline.man.osm_curve.root)
  worker.store.nearby = lambda _position: [Road(lonlat(road()))]
  for _ in range(25):
    result = pipeline()
    worker.step(read_message(worker.shared / 'request.json'), pipeline.now[0])
  assert result.desiredSource == 'route'
  assert 70 < result.desiredSpeed < 90
  assert 'rc=osm/road_matched/matched:' in result.szPosRoadName
  assert not pipeline.man.navi_points_active and not pipeline.man.navi_points
  assert pipeline(45.).desiredSource == 'vturn'
  pipeline.params['OsmCurveSpeedEnabled'] = 0
  assert pipeline().desiredSource != 'route'
  assert pipeline.man.route_curve_speed.speed == 250


def test_navigation_geometry_takes_priority_over_osm(pipeline, tmp_path):
  pipeline.params['OsmCurveSpeedEnabled'] = 1
  worker = OsmWorker(tmp_path / 'maps', pipeline.man.osm_curve.root)

  def forbidden(_position):
    raise AssertionError('OSM must not replace an active navigation route')

  worker.store.nearby = forbidden
  for _ in range(12):
    result = pipeline()
    worker.step(read_message(worker.shared / 'request.json'), pipeline.now[0])
  assert result.desiredSource == 'route'
  assert 'rc=matched:' in result.szPosRoadName
  assert read_message(worker.shared / 'response.json')['status'] == 'navigation_priority'


def test_disabled_osm_does_not_reset_lost_navigation_cap(pipeline):
  for _ in range(12):
    pipeline()
  before = pipeline.man.route_curve_speed.speed
  pipeline.man.navi_points = []
  pipeline.man.navi_points_active = False
  for _ in range(20):
    pipeline()
  after = pipeline.man.route_curve_speed.speed
  assert before <= after < before + 4


def test_osm_uses_device_with_phone_owner_and_known_motorway_width(pipeline, tmp_path):
  pipeline.params['OsmCurveSpeedEnabled'] = 1
  pipeline.man.navi_points = []
  pipeline.man.navi_points_active = False
  worker = OsmWorker(tmp_path / 'maps', pipeline.man.osm_curve.root)
  worker.store.nearby = lambda _position: [Road(lonlat(road() + [0, 6.5]), True, 4, True)]
  for _ in range(25):
    pipeline.serv._gps_sources().put('phone', 25.1, 121.1, 180., 25., pipeline.now[0])
    result = pipeline()
    worker.step(read_message(worker.shared / 'request.json'), pipeline.now[0])
  request = read_message(worker.shared / 'request.json')
  assert result.positionSource == 'phone'  # navigation owner is unchanged
  assert request['position'] == pytest.approx([121.0000124, 25.], abs=.000001)
  assert result.desiredSource == 'route'
  assert '/gps=device/lane=-6.5' in result.szPosRoadName
  assert worker.matcher.lateral_allowance == pytest.approx(7.2)
  pipeline.sm.valid['gpsLocation'] = False
  for _ in range(8):
    pipeline()
    worker.step(read_message(worker.shared / 'request.json'), pipeline.now[0])
  assert read_message(worker.shared / 'request.json')['fix_time'] == -1.
  assert worker.matcher.lateral_allowance == 0.
