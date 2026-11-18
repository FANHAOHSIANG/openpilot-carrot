"""Mapbox search/destination UI and the shared nav-model preview."""
import json
import time
import math
from pathlib import Path

from aiohttp import web

from openpilot.common.params import Params
from ..config import WEB_DIR, CARROT_NAVIGATION_FAVORITES_PATH
from ..services.navigation_favorites import FavoritesFull, NavigationFavorites, google_reference, query_reference
from ..services.static_assets import fingerprint_static_asset
from ..services.params import get_param_value, set_param_value
from openpilot.selfdrive.navigation.preview import PREVIEW_PATH, VIEW_PATH, WEB_DEMAND_PATH, preview_fresh, preview_reason

FAVORITES = web.AppKey('navigation_favorites', NavigationFavorites)


def destination(value):
  if not isinstance(value, dict):
    raise ValueError('invalid destination')
  lat, lon = float(value['latitude']), float(value['longitude'])
  if not math.isfinite(lat) or not math.isfinite(lon) or abs(lat) > 85.05112878 or abs(lon) > 180:
    raise ValueError('invalid coordinates')
  return {'latitude': lat, 'longitude': lon, 'place_name': str(value.get('place_name', 'Destination'))[:256]}


async def page(request):
  html = Path(WEB_DIR, 'navigation.html').read_text(encoding='utf-8')
  for asset in ('/js/pages/navigation_zh_tw.js', '/js/pages/navigation_osm.js', '/js/pages/navigation_map.js'):
    fingerprint = fingerprint_static_asset(WEB_DIR, asset)
    if fingerprint:
      html = html.replace(f'src="{asset}"', f'src="{asset}?v={fingerprint}"')
  return web.Response(text=html, content_type='text/html', headers={'Cache-Control': 'no-store'})


async def map_config(_request):
  return web.json_response({'provider': 'openstreetmap', 'basemaps': ['openstreetmap'],
                            'search': 'disabled', 'routing': 'mapbox', 'model': 'mapsd',
                            'osm_tile_url': 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'},
                           headers={'Cache-Control': 'no-store'})


async def route_view(_request):
  try:
    WEB_DEMAND_PATH.touch()
    if VIEW_PATH.stat().st_size > 512 * 1024:
      raise ValueError('oversized view')
    value = json.loads(VIEW_PATH.read_text(encoding='utf-8'))
    if not isinstance(value, dict) or not 0 <= time.time() - float(value['generated_at']) < 3.:
      raise ValueError('stale view')
  except (OSError, ValueError, KeyError, TypeError, OverflowError):
    value = {'position': None, 'coordinates': [], 'route_id': 0}
  return web.json_response(value, headers={'Cache-Control': 'no-store'})


async def search(request):
  # Keep old clients from accidentally issuing billable geocoding requests.
  return web.json_response({'error': '地址搜尋已停用，避免永久地理編碼費用。請直接輸入經緯度，或分享含座標的 Google Maps 連結。'}, status=410)


async def get_destination(request):
  try:
    value = Params('/dev/shm/params').get('NavDestinationTemporary') or get_param_value('NavDestination', '')
    current = destination(json.loads(value)) if value else None
  except (ValueError, KeyError, TypeError, OverflowError):
    current = None
  return web.json_response({'destination': current, 'map_ready': preview_fresh() and preview_reason() == 'ready',
                            'key_configured': bool(get_param_value('MapboxPublicKey', ''))})


async def set_destination(request):
  try:
    value = destination(await request.json())
  except (ValueError, KeyError, TypeError, OverflowError):
    return web.json_response({'error': 'Invalid destination.'}, status=400)
  Params('/dev/shm/params').remove('NavDestinationTemporary')
  set_param_value('NavDestination', json.dumps(value, ensure_ascii=False))
  set_param_value('NavDestinationWaypoints', '')
  return web.json_response({'destination': value})


def activate_destination(value):
  # Keep the active destination in RAM. Manager clears it when the drive ends.
  set_param_value('NavDestination', '')
  set_param_value('NavDestinationWaypoints', '')
  Params('/dev/shm/params').put('NavDestinationTemporary', json.dumps(value, ensure_ascii=False))


async def favorites(request):
  store = request.app[FAVORITES]
  identifier = request.match_info.get('identifier')
  value = None
  if request.method in ('POST', 'PUT') and not request.path.endswith('/destination'):
    try:
      body = await request.json()
      if isinstance(body, dict) and body.get('provider') == 'query':
        value = query_reference(body)
      else:
        value = google_reference(body) if isinstance(body, dict) and body.get('provider') == 'google' else destination(body)
      if value.get('provider') == 'google':
        # Keep old names editable, but accept no new Google references. Replacing
        # an address requires an explicit Mapbox permanent search in the UI.
        try:
          previous = next((item for item in store.read() if item['id'] == identifier), None) if identifier else None
        except (OSError, ValueError, KeyError, TypeError):
          return web.json_response({'error': 'Favorites are unavailable. Please try again.'}, status=503)
        if previous is None or previous.get('provider') != 'google' or value['google_place_id'] != previous['google_place_id']:
          raise ValueError('Google references are retired')
      name = body.get('name')
      if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
        raise ValueError('invalid name')
      if value.get('provider') not in ('google', 'query') and (not isinstance(body.get('place_name'), str) or not 1 <= len(body['place_name'].strip()) <= 256):
        raise ValueError('invalid address')
      if value.get('provider') not in ('google', 'query') and any(type(body.get(key)) not in (int, float) for key in ('latitude', 'longitude')):
        raise ValueError('invalid coordinates')
      value.update(name=name.strip())
      if value.get('provider') not in ('google', 'query'):
        value['place_name'] = body['place_name'].strip()
    except (ValueError, KeyError, TypeError, OverflowError):
      return web.json_response({'error': 'Invalid favorite.'}, status=400)
  try:
    # Existing saved coordinates may be renamed without another geocode.
    if value is not None and value.get('provider') not in ('google', 'query') and body.get('permanent') is not True and body.get('coordinate_source') != 'manual':
      previous = next((item for item in store.read() if item['id'] == identifier), None) if identifier else None
      if previous is None or any(value[key] != previous[key] for key in ('latitude', 'longitude', 'place_name')):
        return web.json_response({'error': 'Invalid favorite.'}, status=400)
    if request.path.endswith('/destination'):
      saved = next((item for item in store.read() if item['id'] == identifier), None)
      if saved is None:
        raise KeyError(identifier)
      if saved.get('provider') in ('google', 'query'):
        return web.json_response({'error': 'Enter coordinates for this favorite before navigating.'}, status=409)
      target = destination(saved)
      activate_destination(target)
      result = {'destination': target}
    elif request.method == 'GET':
      result = {'favorites': store.read()}
    elif request.method == 'DELETE':
      result = {'favorites': store.delete(identifier)}
    else:
      result = {'favorites': store.save(value, identifier)}
    return web.json_response(result, headers={'Cache-Control': 'no-store'})
  except KeyError:
    return web.json_response({'error': 'Favorite not found.'}, status=404)
  except FavoritesFull:
    return web.json_response({'error': 'You can save up to 100 favorites.'}, status=409)
  except (OSError, ValueError, TypeError, OverflowError):
    return web.json_response({'error': 'Favorites are unavailable. Please try again.'}, status=503)


async def clear_destination(request):
  Params('/dev/shm/params').remove('NavDestinationTemporary')
  set_param_value('NavDestination', '')
  set_param_value('NavDestinationWaypoints', '')
  return web.json_response({'destination': None})


async def preview(request):
  try:
    WEB_DEMAND_PATH.touch()
  except OSError:
    pass
  if not preview_fresh():
    reason = 'waiting' if get_param_value('IsOnroad', False) else 'offroad'
    return web.Response(status=204, headers={'Cache-Control': 'no-store', 'X-Nav-Map-Status': reason})
  return web.FileResponse(PREVIEW_PATH, headers={'Cache-Control': 'no-store', 'X-Nav-Map-Status': preview_reason()})


def register(app):
  app[FAVORITES] = NavigationFavorites(CARROT_NAVIGATION_FAVORITES_PATH)

  from . import google_share
  google_share.register(app)
  app.router.add_get('/navigation', page)
  app.router.add_get('/api/navigation/config', map_config)
  app.router.add_get('/api/navigation/route_view', route_view)
  app.router.add_get('/api/navigation/search', search)
  app.router.add_get('/api/navigation/destination', get_destination)
  app.router.add_post('/api/navigation/destination', set_destination)
  app.router.add_delete('/api/navigation/destination', clear_destination)
  app.router.add_get('/api/navigation/favorites', favorites)
  app.router.add_post('/api/navigation/favorites', favorites)
  app.router.add_put('/api/navigation/favorites/{identifier}', favorites)
  app.router.add_delete('/api/navigation/favorites/{identifier}', favorites)
  app.router.add_post('/api/navigation/favorites/{identifier}/destination', favorites)
  app.router.add_get('/api/navigation/map.png', preview)
