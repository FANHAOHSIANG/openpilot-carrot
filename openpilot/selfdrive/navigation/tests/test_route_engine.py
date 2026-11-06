from concurrent.futures import Future
import json
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from openpilot.selfdrive.navd import navd
from openpilot.selfdrive.navd.helpers import Coordinate, coordinate_from_param


@pytest.fixture
def engine(monkeypatch):
  values = {'MapboxPublicKey': 'pk.test', 'NavDestination': json.dumps({'latitude': 37.01, 'longitude': 127.01})}
  params = NS(get=values.get, remove=lambda key: values.pop(key, None))
  monkeypatch.setattr(navd, 'Params', lambda: params)
  published = []
  engine = navd.RouteEngine(None, NS(send=lambda name, value: published.append((name, value))))
  engine.last_position = Coordinate(37., 127.)
  engine.refresh_token()
  yield engine, values, published
  engine.executor.shutdown(wait=True)


def response():
  return {'routes': [{'legs': [{'annotation': {'maxspeed': [{'speed': 50, 'unit': 'km/h'}]}, 'steps': [
    {'distance': 100., 'duration': 12., 'geometry': {'coordinates': [[127., 37.], [127.01, 37.01]]}},
  ]}]}]}


def pending(engine):
  engine.pending = Future()
  engine.pending_destination = Coordinate(37.01, 127.01)
  engine.pending_token = 'pk.test'
  engine.pending_waypoints = ''


def test_pending_network_never_blocks_or_emits_old_instructions(engine):
  engine, _, published = engine
  pending(engine)
  engine.poll_route()
  engine.send_instruction()
  assert not published[-1][1].valid
  engine.pending.set_result(response())
  engine.poll_route()
  assert engine.step_idx == 0
  assert engine.route_geometry[0][0].annotations['maxspeed'] == pytest.approx(50 / 3.6)


@pytest.mark.parametrize('change', ['destination', 'clear', 'key', 'waypoints'])
def test_late_result_is_discarded_after_user_changes(engine, change):
  engine, values, published = engine
  pending(engine)
  engine.pending.set_result(response())
  if change == 'destination':
    values['NavDestination'] = json.dumps({'latitude': 38., 'longitude': 128.})
  elif change == 'clear':
    values['NavDestination'] = ''
  elif change == 'key':
    values['MapboxPublicKey'] = 'pk.new'
    engine.refresh_token()
  else:
    values['NavDestinationWaypoints'] = '[[127,37]]'
  engine.poll_route()
  assert engine.route is None and engine.pending is None
  assert not published


@pytest.mark.parametrize('value', ['', 'bad json', '[]', '{"latitude":NaN,"longitude":127}'])
def test_invalid_saved_destination_is_cleared(value):
  assert coordinate_from_param('NavDestination', NS(get=lambda _: value)) == (None, None)


def test_destination_change_immediately_clears_old_route_during_request(engine):
  engine, values, published = engine
  pending(engine)
  engine.pending.set_result(response())
  engine.poll_route()
  pending(engine)  # an old reroute is still downloading
  values['NavDestination'] = json.dumps({'latitude': 38., 'longitude': 128.})
  engine.recompute_route()
  engine.send_instruction()
  assert engine.route is None and not published[-1][1].valid
  assert len(published[-2][1].navRouteNavd.coordinates) == 0


def source_update(engine, monkeypatch, *, active=0, external=False, valid=True, alive=True):
  class SubMaster(dict):
    def update(self, _timeout):
      pass

  sm = SubMaster(carrotMan=NS(activeCarrot=active, externalNavigationActive=external))
  sm.updated = {'managerState': False}
  sm.valid = {'carrotMan': valid}
  sm.alive = {'carrotMan': alive}
  engine.sm = sm
  engine.gps_ok = True
  engine.resend_at = 0.
  for name in ('update_location', 'recompute_route', 'send_instruction', 'clear_route', 'reset_recompute_limits'):
    monkeypatch.setattr(engine, name, Mock())
  return sm


@pytest.mark.parametrize('active', range(7))
def test_stock_warning_does_not_suppress_coordinate_route(engine, monkeypatch, active):
  engine, _, _ = engine
  source_update(engine, monkeypatch, active=active)
  engine.update()
  engine.recompute_route.assert_called_once()
  engine.send_instruction.assert_called_once()


@pytest.mark.parametrize('active', [0, 1, 2, 5])
def test_external_session_owns_navigation_without_a_current_maneuver(engine, monkeypatch, active):
  engine, _, published = engine
  source_update(engine, monkeypatch, active=active, external=True)
  engine.update()
  engine.recompute_route.assert_not_called()
  engine.send_instruction.assert_not_called()
  assert published[-1][0] == 'navInstruction' and not published[-1][1].valid


@pytest.mark.parametrize('valid,alive', [(False, True), (True, False), (False, False)])
def test_invalid_or_stale_external_source_cannot_block_navigation(engine, monkeypatch, valid, alive):
  engine, _, _ = engine
  source_update(engine, monkeypatch, external=True, valid=valid, alive=alive)
  engine.update()
  engine.recompute_route.assert_called_once()


def test_external_disconnect_recomputes_saved_route_once(engine, monkeypatch):
  engine, _, _ = engine
  sm = source_update(engine, monkeypatch, active=3, external=True)
  engine.update()
  sm['carrotMan'].externalNavigationActive = False
  engine.update()
  engine.update()
  engine.clear_route.assert_called_once()
  engine.reset_recompute_limits.assert_called_once()
  assert engine.recompute_route.call_count == 2


def test_stock_warning_does_not_bypass_gps_requirement(engine, monkeypatch):
  engine, _, published = engine
  source_update(engine, monkeypatch, active=3)
  engine.gps_ok = False
  engine.update()
  engine.recompute_route.assert_not_called()
  assert not published[-1][1].valid


def test_explicit_source_roundtrips_separately_from_warning_state():
  message = navd.messaging.new_message('carrotMan', valid=True)
  message.carrotMan.activeCarrot = 5
  assert not message.carrotMan.externalNavigationActive
  message.carrotMan.externalNavigationActive = True
  with navd.log.Event.from_bytes(message.to_bytes()) as reader:
    assert reader.carrotMan.externalNavigationActive
    assert reader.carrotMan.activeCarrot == 5
