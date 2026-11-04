"""Mapbox search/destination UI and the shared nav-model preview."""
import json
import math
from pathlib import Path

from aiohttp import web

from ..config import WEB_DIR
from ..services.params import get_param_value, set_param_value
from openpilot.selfdrive.navigation.preview import PREVIEW_PATH, WEB_DEMAND_PATH, preview_fresh, preview_reason

def destination(value):
  if not isinstance(value, dict):
    raise ValueError('invalid destination')
  lat, lon = float(value['latitude']), float(value['longitude'])
  if not math.isfinite(lat) or not math.isfinite(lon) or abs(lat) > 85.05112878 or abs(lon) > 180:
    raise ValueError('invalid coordinates')
  return {'latitude': lat, 'longitude': lon, 'place_name': str(value.get('place_name', 'Destination'))[:256]}


async def page(request):
  return web.FileResponse(str(Path(WEB_DIR) / 'navigation.html'), headers={'Cache-Control': 'no-cache'})


async def search(request):
  # Keep old clients from accidentally issuing billable geocoding requests.
  return web.json_response({'error': '地址搜尋已停用，避免永久地理編碼費用。請直接輸入經緯度，或分享含座標的 Google Maps 連結。'}, status=410)


async def get_destination(request):
  try:
    value = get_param_value('NavDestination', '')
    current = destination(json.loads(value)) if value else None
  except (ValueError, KeyError, TypeError):
    current = None
  return web.json_response({'destination': current, 'map_ready': preview_fresh() and preview_reason() == 'ready',
                            'key_configured': bool(get_param_value('MapboxPublicKey', ''))})


async def set_destination(request):
  try:
    value = destination(await request.json())
  except (ValueError, KeyError, TypeError):
    return web.json_response({'error': 'Invalid destination.'}, status=400)
  set_param_value('NavDestination', json.dumps(value, ensure_ascii=False))
  set_param_value('NavDestinationWaypoints', '')
  return web.json_response({'destination': value})


async def clear_destination(request):
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
  from . import google_share
  google_share.register(app)
  app.router.add_get('/navigation', page)
  app.router.add_get('/api/navigation/search', search)
  app.router.add_get('/api/navigation/destination', get_destination)
  app.router.add_post('/api/navigation/destination', set_destination)
  app.router.add_delete('/api/navigation/destination', clear_destination)
  app.router.add_get('/api/navigation/map.png', preview)
