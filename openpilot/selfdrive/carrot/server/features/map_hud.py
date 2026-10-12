"""Web-only CPdazi map projection settings."""
import asyncio
from pathlib import Path
from aiohttp import web
from openpilot.selfdrive.carrot import map_hud

PAGE = Path(__file__).resolve().parents[2] / 'web/map-hud.html'


async def page(_request):
  return web.FileResponse(PAGE)


async def get_config(_request):
  return web.json_response({'config': map_hud.read_config(), 'status': map_hud.read_status()})


async def set_config(request):
  try:
    if request.content_length is not None and request.content_length > 4096:
      raise ValueError('settings too large')
    raw = await request.read()
    if len(raw) > 4096:
      raise ValueError('settings too large')
    import json
    body = json.loads(raw)
    config = await asyncio.to_thread(map_hud.save_config, body)
    return web.json_response({'config': config, 'status': map_hud.read_status()})
  except (ValueError, TypeError) as exc:
    return web.json_response({'error': str(exc)}, status=400)


def register(app):
  app.router.add_get('/map-hud', page)
  app.router.add_get('/api/map_hud', get_config)
  app.router.add_post('/api/map_hud', set_config)
