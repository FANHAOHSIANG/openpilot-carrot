import asyncio
import json

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from openpilot.selfdrive.carrot.server.features import navigation


def test_destination_lifecycle_and_validation(monkeypatch):
  values = {}
  monkeypatch.setattr(navigation, 'get_param_value', lambda key, default: values.get(key, default))
  monkeypatch.setattr(navigation, 'set_param_value', lambda key, value: values.__setitem__(key, value))

  async def run():
    app = web.Application()
    navigation.register(app)
    async with TestClient(TestServer(app)) as client:
      response = await client.post('/api/navigation/destination', json={'latitude': 37., 'longitude': 127., 'place_name': '<script>name</script>'})
      assert response.status == 200
      assert json.loads(values['NavDestination'])['place_name'] == '<script>name</script>'
      response = await client.get('/api/navigation/destination')
      assert (await response.json())['destination']['latitude'] == 37.
      for payload in ([], {}, {'latitude': 91, 'longitude': 127}, {'latitude': None, 'longitude': 0}):
        assert (await client.post('/api/navigation/destination', json=payload)).status == 400
      assert (await client.get('/api/navigation/search?q=Seoul')).status == 410
      assert (await client.delete('/api/navigation/destination')).status == 200
      assert values['NavDestination'] == ''
  asyncio.run(run())


def test_navigation_page_is_served():
  async def run():
    app = web.Application()
    navigation.register(app)
    async with TestClient(TestServer(app)) as client:
      response = await client.get('/navigation')
      assert response.status == 200
      assert 'navigation_map.js' in await response.text()
  asyncio.run(run())


@pytest.mark.parametrize('fresh,reason,ready', [
  (True, 'route', False), (True, 'position', False), (True, 'ready', True), (False, 'ready', False),
])
def test_destination_requires_usable_preview(monkeypatch, fresh, reason, ready):
  monkeypatch.setattr(navigation, 'get_param_value', lambda key, default: default)
  monkeypatch.setattr(navigation, 'preview_fresh', lambda: fresh)
  monkeypatch.setattr(navigation, 'preview_reason', lambda: reason)
  response = asyncio.run(navigation.get_destination(None))
  assert json.loads(response.text)['map_ready'] is ready


@pytest.mark.parametrize('onroad,reason', [(False, 'offroad'), (True, 'waiting')])
def test_missing_preview_explains_service_state(monkeypatch, tmp_path, onroad, reason):
  demand = tmp_path / 'demand'
  monkeypatch.setattr(navigation, 'WEB_DEMAND_PATH', demand)
  monkeypatch.setattr(navigation, 'preview_fresh', lambda: False)
  monkeypatch.setattr(navigation, 'get_param_value', lambda key, default: onroad if key == 'IsOnroad' else default)
  response = asyncio.run(navigation.preview(None))
  assert response.status == 204
  assert response.headers['X-Nav-Map-Status'] == reason
  assert response.headers['Cache-Control'] == 'no-store'
  assert demand.exists()


def test_search_is_disabled_without_outbound_requests(monkeypatch):
  def unexpected(*args, **kwargs):
    raise AssertionError('Disabled search must never access a token or HTTP client')
  monkeypatch.setattr(navigation, 'get_param_value', unexpected)
  async def run():
    app = web.Application()
    navigation.register(app)
    async with TestClient(TestServer(app)) as client:
      for query in ('Seoul', '24.8,121.0', ''):
        response = await client.get('/api/navigation/search', params={'q': query})
        assert response.status == 410
  asyncio.run(run())
