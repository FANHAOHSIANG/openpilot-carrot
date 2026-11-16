import asyncio
import json
from types import SimpleNamespace as NS

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from openpilot.selfdrive.carrot.server.features import navigation


@pytest.fixture(autouse=True)
def temporary_params(monkeypatch):
  values = {}
  def params(path):
    assert path == '/dev/shm/params'
    return NS(get=values.get, put=values.__setitem__, remove=lambda key: values.pop(key, None))
  monkeypatch.setattr(navigation, 'Params', params)
  return values


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
      assert response.headers['Cache-Control'] == 'no-store'
      assert 'navigation_map.js?v=' in await response.text()
  asyncio.run(run())


def test_favorite_limit_and_stale_id_do_not_overwrite_other_favorites(monkeypatch, tmp_path):
  path = tmp_path / 'favorites.json'
  monkeypatch.setattr(navigation, 'CARROT_NAVIGATION_FAVORITES_PATH', str(path))
  existing = [dict(id=f'{i:032x}', name=f'最愛{i}', place_name='地址', latitude=25., longitude=121.) for i in range(100)]
  path.write_text(json.dumps(existing, ensure_ascii=False), encoding='utf-8')
  async def run():
    app = web.Application(); navigation.register(app)
    async with TestClient(TestServer(app)) as client:
      new = dict(name='新最愛', place_name='地址', latitude=25., longitude=121., permanent=True)
      assert (await client.post('/api/navigation/favorites', json=new)).status == 409
      assert json.loads(path.read_text(encoding='utf-8')) == existing
      assert (await client.put('/api/navigation/favorites/missing', json=new)).status == 404
      assert (await client.delete('/api/navigation/favorites/missing')).status == 404
      assert (await client.put('/api/navigation/favorites/' + existing[0]['id'], json=new)).status == 200
      saved = json.loads(path.read_text(encoding='utf-8'))
      assert len(saved) == 100 and saved[0]['name'] == '新最愛' and saved[1:] == existing[1:]
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


def test_favorites_crud_persistence_and_navigation(monkeypatch, tmp_path, temporary_params):
  path = tmp_path / 'favorites.json'
  monkeypatch.setattr(navigation, 'CARROT_NAVIGATION_FAVORITES_PATH', str(path))
  monkeypatch.setattr(navigation, 'set_param_value', lambda *args: None)
  async def run():
    app = web.Application(); navigation.register(app)
    async with TestClient(TestServer(app)) as client:
      assert (await (await client.get('/api/navigation/favorites')).json()) == {'favorites': []}
      place = {'name': '家 🏠', 'place_name': '臺北市測試路', 'latitude': 25., 'longitude': 121., 'permanent': True}
      response = await client.post('/api/navigation/favorites', json=place)
      assert response.status == 200 and response.headers['Cache-Control'] == 'no-store'
      identifier = (await response.json())['favorites'][0]['id']
      assert not temporary_params  # Saving does not start navigation.
      renamed = dict(place, name='公司', permanent=False)
      assert (await client.put('/api/navigation/favorites/' + identifier, json=renamed)).status == 200
      changed = dict(place, name='公司', latitude=24., place_name='新竹市新地址')
      assert (await client.put('/api/navigation/favorites/' + identifier, json=changed)).status == 200
      assert not temporary_params
    # A new application instance reads the same persisted favorite.
    app = web.Application(); navigation.register(app)
    async with TestClient(TestServer(app)) as client:
      saved = (await (await client.get('/api/navigation/favorites')).json())['favorites']
      assert len(saved) == 1 and saved[0]['name'] == '公司' and saved[0]['latitude'] == 24.
      assert (await client.post('/api/navigation/favorites/' + identifier + '/destination')).status == 200
      active = json.loads(temporary_params['NavDestinationTemporary'])
      assert active['latitude'] == 24. and active['place_name'] == '新竹市新地址'
      assert (await client.delete('/api/navigation/favorites/' + identifier)).status == 200
      assert json.loads(temporary_params['NavDestinationTemporary']) == active  # Deleting a favorite does not end a drive.
      assert (await client.post('/api/navigation/favorites/' + identifier + '/destination')).status == 404
      assert (await client.delete('/api/navigation/destination')).status == 200
      assert not temporary_params
      assert (await (await client.get('/api/navigation/favorites')).json()) == {'favorites': []}
  asyncio.run(run())


def test_favorites_reject_bad_input_and_preserve_file_on_failure(monkeypatch, tmp_path):
  path = tmp_path / 'favorites.json'
  monkeypatch.setattr(navigation, 'CARROT_NAVIGATION_FAVORITES_PATH', str(path))
  async def run():
    app = web.Application(); navigation.register(app)
    async with TestClient(TestServer(app)) as client:
      valid = {'name': '家', 'place_name': '測試地址', 'latitude': 25., 'longitude': 121., 'permanent': True}
      for updates in ({'name': ''}, {'name': 'x' * 81}, {'latitude': True}, {'longitude': 181},
                      {'latitude': None}, {'place_name': ''}, {'permanent': False}):
        assert (await client.post('/api/navigation/favorites', json=dict(valid, **updates))).status == 400
      assert (await client.post('/api/navigation/favorites', data='{', headers={'Content-Type':'application/json'})).status == 400
      assert not path.exists()
      assert (await client.post('/api/navigation/favorites', json=valid)).status == 200
      original = path.read_bytes()
      monkeypatch.setattr('openpilot.selfdrive.carrot.server.services.navigation_favorites.os.replace',
                          lambda *_: (_ for _ in ()).throw(OSError('disk error')))
      assert (await client.post('/api/navigation/favorites', json=valid)).status == 503
      assert path.read_bytes() == original
      assert list(tmp_path.iterdir()) == [path]
      path.write_text('broken', encoding='utf-8')
      assert (await client.get('/api/navigation/favorites')).status == 503
      assert (await client.post('/api/navigation/favorites', json=valid)).status == 503
      assert path.read_text(encoding='utf-8') == 'broken'
  asyncio.run(run())


def test_manual_coordinate_favorite_and_destination_replace_temporary(monkeypatch, tmp_path, temporary_params):
  monkeypatch.setattr(navigation, 'CARROT_NAVIGATION_FAVORITES_PATH', str(tmp_path / 'favorites.json'))
  values = {}
  monkeypatch.setattr(navigation, 'get_param_value', lambda key, default: values.get(key, default))
  monkeypatch.setattr(navigation, 'set_param_value', lambda key, value: values.__setitem__(key, value))

  async def run():
    app = web.Application(); navigation.register(app)
    async with TestClient(TestServer(app)) as client:
      place = dict(name='手動座標', place_name='25,121', latitude=25., longitude=121., coordinate_source='manual')
      response = await client.post('/api/navigation/favorites', json=place)
      assert response.status == 200
      identifier = (await response.json())['favorites'][0]['id']
      assert not temporary_params
      assert (await client.post(f'/api/navigation/favorites/{identifier}/destination')).status == 200
      assert 'NavDestinationTemporary' in temporary_params
      direct = dict(latitude=24., longitude=120., place_name='24,120')
      assert (await client.post('/api/navigation/destination', json=direct)).status == 200
      assert not temporary_params
      assert (await (await client.get('/api/navigation/destination')).json())['destination'] == direct
      assert (await client.get('/api/navigation/search?q=test&permanent=true')).status == 410
  asyncio.run(run())
