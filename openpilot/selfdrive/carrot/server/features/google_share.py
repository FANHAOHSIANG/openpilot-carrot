"""Paired, confirmation-only Google Maps destination import (not route mirroring)."""
import asyncio
import hashlib
import hmac
import json
import math
from pathlib import Path
import re
import secrets
import time
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

import aiohttp
from aiohttp import web

from ..config import CARROT_STATE_DIR, WEB_DIR
from ..services.params import set_param_value

PAIR_PATH = Path(CARROT_STATE_DIR) / 'google-share-pair.json'
GOOGLE_HOSTS = frozenset(('google.com', 'www.google.com', 'maps.google.com',
                          'google.com.tw', 'www.google.com.tw', 'maps.google.com.tw'))
SHORT_HOSTS = frozenset(('maps.app.goo.gl', 'goo.gl'))


def write_pair(value, path=None):
  path = Path(path or PAIR_PATH)
  path.parent.mkdir(parents=True, exist_ok=True)
  pending = path.with_name(path.name + '.tmp')
  # Credentials never enter Params, URLs, the repository or request logs.
  import os
  fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
  try:
    with os.fdopen(fd, 'w') as out:
      os.fchmod(out.fileno(), 0o600)
      json.dump(value, out)
    pending.replace(path)
  finally:
    pending.unlink(missing_ok=True)


def read_pair():
  try:
    value = json.loads(PAIR_PATH.read_text())
    return value if isinstance(value, dict) else {}
  except (OSError, ValueError):
    return {}


def validate_url(value):
  if not isinstance(value, str) or len(value) > 4096:
    raise ValueError('Google Maps 連結過長或格式錯誤。')
  # Sharing often includes a place name before the URL.
  matches = re.findall(r'https://[^\s<>]+', value)
  if len(matches) != 1:
    raise ValueError('請貼上一個 Google Maps 分享連結。')
  value = matches[0]
  parts = urlsplit(value)
  try:
    port = parts.port
  except ValueError:
    raise ValueError('不支援的連結。') from None
  if (parts.scheme != 'https' or parts.username or parts.password or port not in (None, 443)
      or parts.hostname not in GOOGLE_HOSTS | SHORT_HOSTS):
    raise ValueError('只接受 HTTPS Google Maps 連結。')
  maps_root = parts.hostname.startswith('maps.google.') and parts.path in ('', '/')
  if parts.hostname in GOOGLE_HOSTS and not (maps_root or parts.path == '/maps' or parts.path.startswith('/maps/')):
    raise ValueError('這不是 Google Maps 地點連結。')
  if parts.hostname == 'goo.gl' and not parts.path.startswith('/maps/'):
    raise ValueError('只接受 goo.gl/maps 地圖短網址。')
  return value


def point(text, name):
  values = text.split(',')
  if len(values) != 2:
    return None
  try:
    lat, lon = map(float, values)
  except ValueError:
    return None
  if not math.isfinite(lat) or not math.isfinite(lon) or abs(lat) > 85.05112878 or abs(lon) > 180:
    raise ValueError('地點座標無效。')
  return {'latitude': lat, 'longitude': lon, 'place_name': name[:256]}


def parse_place(url):
  url = validate_url(url)
  parts = urlsplit(url)
  q = parse_qs(parts.query)
  # Only destination/POI coordinates are accepted. /@lat,lon is a camera center.
  for key in ('destination', 'daddr', 'query', 'q'):
    if q.get(key):
      value = q[key][0].strip()
      found = point(value, value)
      return {'destination': found} if found else {'query': value[:200]}
  path = unquote(parts.path)
  label = re.search(r'/place/([^/]+)', path)
  label = label[1].replace('+', ' ') if label else 'Google Maps 地點'
  coords = set(re.findall(r'!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)', unquote(url)))
  if len(coords) == 1:
    lat, lon = next(iter(coords))
    return {'destination': point(f'{lat},{lon}', label)}
  if label != 'Google Maps 地點':
    return {'query': label[:200]}
  raise ValueError('連結沒有明確目的地，請改分享單一地點，或貼上地址搜尋。')


async def resolve_url(http, raw):
  url = validate_url(raw)
  for _ in range(6):
    if urlsplit(url).hostname in GOOGLE_HOSTS:
      return parse_place(url)
    async with http.get(url, allow_redirects=False, timeout=aiohttp.ClientTimeout(total=5)) as response:
      if response.status not in (301, 302, 303, 307, 308):
        raise ValueError('無法展開地圖短網址，請改貼完整 Google Maps 網址或地址。')
      location = response.headers.get('Location', '')
      if not location:
        raise ValueError('地圖短網址沒有目的地。')
      url = validate_url(urljoin(url, location))
  raise ValueError('地圖短網址轉址次數過多。')


class ShareState:
  def __init__(self):
    self.lock = asyncio.Lock()
    self.attempts = []
    self.next_resolve = 0.


STATE = web.AppKey('google_share', ShareState)


def authorized(request):
  header = request.headers.get('Authorization', '')
  token = header[7:] if header.startswith('Bearer ') else ''
  expected = read_pair().get('token_sha256', '')
  return bool(token and expected and hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), expected))


async def page(request):
  return web.FileResponse(Path(WEB_DIR) / 'google-share.html', headers={'Cache-Control': 'no-store'})


async def pair(request):
  state = request.app[STATE]
  async with state.lock:
    now = time.time()
    state.attempts = [t for t in state.attempts if now - t < 60]
    if len(state.attempts) >= 5:
      return web.json_response({'error': '配對嘗試過多，請等一分鐘。'}, status=429)
    state.attempts.append(now)
    try:
      code = (await request.json()).get('code', '')
    except (ValueError, AttributeError):
      code = ''
    saved = read_pair()
    if (not isinstance(code, str) or not re.fullmatch(r'\d{6}', code)
        or now >= saved.get('expires', 0) or not saved.get('code_sha256')
        or not hmac.compare_digest(hashlib.sha256(code.encode()).hexdigest(), saved['code_sha256'])):
      return web.json_response({'error': '配對碼錯誤或已過期，請在 C4 重新產生。'}, status=403)
    token = secrets.token_urlsafe(32)
    write_pair({'token_sha256': hashlib.sha256(token.encode()).hexdigest()})
    return web.json_response({'token': token}, headers={'Cache-Control': 'no-store'})


async def resolve(request):
  if not authorized(request):
    return web.json_response({'error': '請先配對這支手機。'}, status=401)
  state = request.app[STATE]
  if state.lock.locked() or time.monotonic() < state.next_resolve:
    return web.json_response({'error': '請稍候再試。'}, status=429)
  async with state.lock:
    state.next_resolve = time.monotonic() + 1
    try:
      raw = (await request.json()).get('url', '')
      result = await asyncio.wait_for(resolve_url(request.app['http'], raw), timeout=12)
      return web.json_response(result, headers={'Cache-Control': 'no-store'})
    except (ValueError, AttributeError) as error:
      return web.json_response({'error': str(error)}, status=400)
    except (aiohttp.ClientError, TimeoutError):
      return web.json_response({'error': 'Google Maps 連結暫時無法解析，請改用地址搜尋。'}, status=502)


async def confirm(request):
  if not authorized(request):
    return web.json_response({'error': '請先配對這支手機。'}, status=401)
  from .navigation import destination
  try:
    value = destination(await request.json())
  except (ValueError, KeyError, TypeError, OverflowError):
    return web.json_response({'error': '目的地格式錯誤。'}, status=400)
  set_param_value('NavDestination', json.dumps(value, ensure_ascii=False))
  set_param_value('NavDestinationWaypoints', '')
  return web.json_response({'destination': value}, headers={'Cache-Control': 'no-store'})


def register(app):
  app[STATE] = ShareState()
  app.router.add_get('/navigation/share', page)
  app.router.add_post('/api/navigation/share/pair', pair)
  app.router.add_post('/api/navigation/share/resolve', resolve)
  app.router.add_post('/api/navigation/share/confirm', confirm)


if __name__ == '__main__':
  code = f'{secrets.randbelow(1000000):06d}'
  write_pair({'code_sha256': hashlib.sha256(code.encode()).hexdigest(), 'expires': time.time() + 600})
  print('Google Maps 分享配對碼（10 分鐘內有效、限用一次）：' + code)
  print('在手機以原本 Carrot 網頁的主機與連接埠開啟 /navigation/share，輸入配對碼。')
  print('新配對會取代舊配對。此功能只分享目的地，由 Carrot 重新計算路線。')
