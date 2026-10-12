"""CPdazi JPEG projection to the existing Navi media bus (display only)."""
from __future__ import annotations

import hashlib
import io
import ipaddress
import json
import os
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

CONFIG_PATH = Path(os.environ.get('CARROT_DATA_DIR', '/data/carrot')) / 'state/map_hud.json'
STATUS_PATH = Path('/dev/shm/carrot-map-hud-status.json')
MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_OUTPUT_BYTES = 128 * 1024
STALE_SECONDS = 3.0
DEFAULT_CONFIG = {'enabled': False, 'frame_url': '', 'fps': 2}
_CONFIG_LOCK = threading.Lock()


def normalize_config(raw):
  if not isinstance(raw, dict):
    raise ValueError('settings must be an object')
  enabled = raw.get('enabled', False)
  if not isinstance(enabled, bool):
    raise ValueError('enabled must be boolean')
  fps = raw.get('fps', 2)
  if isinstance(fps, bool) or not isinstance(fps, int) or not 1 <= fps <= 5:
    raise ValueError('fps must be an integer from 1 to 5')
  url = str(raw.get('frame_url', '')).strip()
  if url:
    p = urlsplit(url)
    try:
      ip = ipaddress.ip_address(p.hostname or '')
      port = p.port
    except ValueError as exc:
      raise ValueError('use the projection device local IP and port') from exc
    if p.scheme != 'http' or p.username or p.password or p.fragment or p.query:
      raise ValueError('use a plain local HTTP projection URL without credentials or query')
    if not ip.is_private or ip.is_loopback or ip.is_unspecified or ip.is_multicast or ip.is_link_local:
      raise ValueError('projection address must be a private LAN IP')
    if port is None or not 1 <= port <= 65535:
      raise ValueError('include the projection port shown by CPdazi')
    path = p.path.rstrip('/')
    if path not in ('', '/frame'):
      raise ValueError('use the projection base URL or /frame, not /stream')
    url = urlunsplit(('http', p.netloc, '/frame', '', ''))
  if enabled and not url:
    raise ValueError('enter the CPdazi projection URL before enabling')
  return {'enabled': enabled, 'frame_url': url, 'fps': fps}


def read_config():
  try:
    return normalize_config(json.loads(CONFIG_PATH.read_text()))
  except (OSError, ValueError, TypeError):
    return dict(DEFAULT_CONFIG)


def atomic_json(path, value):
  path.parent.mkdir(parents=True, exist_ok=True)
  tmp = path.with_suffix('.tmp')
  tmp.write_text(json.dumps(value, ensure_ascii=False) + '\n')
  tmp.replace(path)


def save_config(raw):
  config = normalize_config(raw)
  with _CONFIG_LOCK:
    atomic_json(CONFIG_PATH, config)
  return config


def read_status():
  try:
    status = json.loads(STATUS_PATH.read_text())
    status['worker_alive'] = time.monotonic() - status.get('updated_mono', 0) < 5
    return status
  except (OSError, ValueError, TypeError):
    return {'state': 'not_running', 'worker_alive': False}


class NoRedirect(HTTPRedirectHandler):
  def redirect_request(self, req, fp, code, msg, headers, newurl):
    raise ValueError('projection redirects are not supported')


def fetch_frame(url):
  opener = build_opener(ProxyHandler({}), NoRedirect())
  start = time.monotonic()
  with opener.open(Request(url, headers={'Cache-Control': 'no-cache'}), timeout=1.5) as response:
    if response.headers.get_content_type() != 'image/jpeg':
      raise ValueError('source is not a JPEG /frame endpoint')
    chunks = []
    size = 0
    while True:
      chunk = response.read(min(16384, MAX_INPUT_BYTES + 1 - size))
      if not chunk:
        break
      chunks.append(chunk)
      size += len(chunk)
      if size > MAX_INPUT_BYTES or time.monotonic() - start > 2.0:
        raise ValueError('projection frame exceeds size/time limit')
    data = b''.join(chunks)
    if not data:
      raise ValueError('projection has no frame; start CPdazi projection')
    source_id = (response.headers.get('X-Frame-Sequence', '') + ':' + hashlib.sha256(data).hexdigest())
    return data, source_id


def prepare_jpeg(data):
  from PIL import Image
  with Image.open(io.BytesIO(data)) as image:
    if image.format != 'JPEG' or image.width * image.height > 8_000_000:
      raise ValueError('invalid or oversized JPEG')
    image.thumbnail((800, 480), Image.Resampling.BILINEAR)
    image = image.convert('RGB')
    for quality in (65, 45, 25):
      out = io.BytesIO()
      image.save(out, format='JPEG', quality=quality)
      if out.tell() <= MAX_OUTPUT_BYTES:
        return out.getvalue(), image.width, image.height
  raise ValueError('compressed projection frame exceeds transport budget')


class MapHudBridge:
  """Network/decode work runs outside the publisher and inference loops."""
  def __init__(self, receiver, fetch=fetch_frame, prepare=prepare_jpeg):
    self.receiver = receiver
    self.fetch = fetch
    self.prepare = prepare
    self.stop_event = threading.Event()
    self.thread = None
    self.last_id = None
    self.last_good = 0.0
    self.last_config = None
    self.frames = 0
    self.last_session = ''

  def start(self):
    self.thread = threading.Thread(target=self.run, name='cp_map_hud', daemon=True)
    self.thread.start()

  def stop(self):
    self.stop_event.set()
    if self.thread is not None:
      self.thread.join(timeout=3)
    self.receiver.record_projection_frame(self.last_session, None)

  def tick(self, config):
    now = time.monotonic()
    if config != self.last_config:
      self.receiver.record_projection_frame(self.last_session, None)
      self.last_id = None
      self.last_good = 0.0
      self.last_config = dict(config)
    if not config['enabled']:
      return {'state': 'disabled'}
    session = self.receiver.cereal_snapshot()
    if not session['connected'] or not session['session_id']:
      self.receiver.record_projection_frame(self.last_session, None)
      self.last_id = None
      return {'state': 'waiting_navigation', 'detail': 'Connect CPdazi Navi v2 to this comma first'}
    if session['session_id'] != self.last_session:
      self.last_id = None
      self.last_good = 0.0
    self.last_session = session['session_id']
    try:
      data, source_id = self.fetch(config['frame_url'])
      if source_id == self.last_id:
        if now - self.last_good >= STALE_SECONDS:
          self.receiver.record_projection_frame(self.last_session, None)
          return {'state': 'stalled', 'detail': 'Projection frame stopped updating'}
        return {'state': 'streaming', 'frames': self.frames}
      payload, width, height = self.prepare(data)
      accepted = self.receiver.record_projection_frame(self.last_session, (payload, width, height))
      if not accepted:
        return {'state': 'native_map_or_session_changed'}
      self.last_id = source_id
      self.last_good = time.monotonic()
      self.frames += 1
      return {'state': 'streaming', 'frames': self.frames, 'bytes': len(payload), 'width': width, 'height': height}
    except Exception as exc:
      if time.monotonic() - self.last_good >= STALE_SECONDS:
        self.receiver.record_projection_frame(self.last_session, None)
      return {'state': 'source_error', 'detail': str(exc)[:180], 'frames': self.frames}

  def run(self):
    while not self.stop_event.is_set():
      started = time.monotonic()
      config = read_config()
      try:
        status = self.tick(config)
        atomic_json(STATUS_PATH, {**status, 'updated_mono': time.monotonic()})
      except Exception:
        pass  # Display diagnostics must never stop the navigation receiver.
      self.stop_event.wait(max(0.05, 1 / config['fps'] - (time.monotonic() - started)))
