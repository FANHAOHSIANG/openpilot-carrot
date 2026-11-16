"""Small atomic shared-memory mailbox between CarrotMan and the OSM worker."""
import json
import math
from pathlib import Path
import uuid

SHARED_PATH = Path('/dev/shm/carrot_osm')
MAX_MESSAGE = 256 * 1024


def read_message(path):
  try:
    with Path(path).open('rb') as file:
      data = file.read(MAX_MESSAGE + 1)
    value = json.loads(data) if len(data) <= MAX_MESSAGE else None
    return value if isinstance(value, dict) else {}
  except (OSError, ValueError, TypeError):
    return {}


def write_message(path, data):
  path = Path(path)
  path.parent.mkdir(parents=True, exist_ok=True)
  encoded = json.dumps(data, allow_nan=False, separators=(',', ':'))
  if len(encoded) > MAX_MESSAGE:
    raise ValueError('oversized_osm_message')
  temporary = path.with_suffix('.tmp')
  temporary.write_text(encoded)
  temporary.replace(path)


def fresh_request(request, now):
  try:
    stamp = request['stamp']
    return isinstance(request['session'], str) and math.isfinite(stamp) and 0 <= now - stamp <= 1.5
  except (KeyError, TypeError, ValueError):
    return False


def valid_position(request, now):
  try:
    lon, lat = request['position']
    values = (lon, lat, request['heading'], request['fix_time'], request['speed'])
    return (all(math.isfinite(x) for x in values) and abs(lon) <= 180 and abs(lat) <= 85
            and 0 <= now - request['fix_time'] <= 1.5 and 2 <= request['speed'] <= 90)
  except (KeyError, TypeError, ValueError):
    return False


class OsmCurveClient:
  def __init__(self, root=SHARED_PATH):
    self.root = Path(root)
    self.session = uuid.uuid4().hex
    self.next_update = 0.
    self.response = {}
    self.status = 'starting'
    self.mode = None
    self.lateral_allowance = 0.

  def update(self, *, now, onroad, enabled, wanted, wifi, position, heading, fix_time, speed):
    mode = (onroad, enabled, wanted, wifi)
    if now >= self.next_update or mode != self.mode:
      self.next_update = now + .2
      self.mode = mode
      request = {'session': self.session, 'stamp': now, 'onroad': onroad, 'enabled': enabled,
                 'wanted': wanted, 'wifi': wifi, 'position': position, 'heading': heading, 'fix_time': fix_time, 'speed': speed}
      try:
        write_message(self.root / 'request.json', request)
        self.response = read_message(self.root / 'response.json')
      except (OSError, ValueError, TypeError):
        self.response = {}
    self.lateral_allowance = 0.
    response = self.response
    self.status = str(response.get('status', 'worker_wait'))[:80]
    if not enabled or not wanted or not onroad:
      return (), 'inactive'
    try:
      # Replies are tied to this CarrotMan instance and the original request
      # time, not the later decode completion time. A dead worker expires.
      age = now - response['stamp']
      if response['session'] != self.session or not math.isfinite(age) or not 0 <= age <= 1.0:
        self.status = 'stale_worker'
        return (), self.status
      points = response.get('points', ())
      if not 3 <= len(points) <= 4096:
        return (), self.status
      allowance = response.get('lateral_allowance', 0.)
      if not isinstance(allowance, (int, float)) or not math.isfinite(allowance) or not 0 <= allowance <= 7.2:
        self.status = 'invalid_road_width'
        return (), self.status
      self.lateral_allowance = allowance
      return points, str(response['id'])[:64]
    except (KeyError, TypeError, ValueError):
      self.status = 'worker_wait'
      return (), self.status
