"""Read existing Jetlink display packets; never open a camera or a CAN socket."""
import base64
from io import BytesIO
import json
import math
from pathlib import Path
import struct

import numpy as np
from PIL import Image

HEADER = struct.Struct('<d')
MAX_PACKET = 512 * 1024
TTL = .8


def read_packet(path, now):
  try:
    with Path(path).open('rb') as f:
      raw = f.read(MAX_PACKET + 1)
    if not HEADER.size < len(raw) <= MAX_PACKET:
      return None
    received, = HEADER.unpack_from(raw)
    packet = json.loads(raw[HEADER.size:])
    if (not isinstance(packet, dict) or packet.get('version') != 1 or
        not 0 <= now - received < .5 or not math.isfinite(packet['sent'])):
      return None
    return received, packet
  except (OSError, ValueError, KeyError, TypeError, struct.error):
    return None


class Frames:
  def __init__(self):
    self.last_key = None

  def take(self, snapshot, now):
    if snapshot is None:
      return None
    received, packet = snapshot
    try:
      if packet.get('params', {}).get('IsOnroad') != 'MQ==':
        return None
      frame = packet['cameras']['road']
      fid, captured = frame['frame'], frame['capture_time']
      w, h = frame['width'], frame['height']
      sw, sh = frame['source_width'], frame['source_height']
      key = (fid, captured, sw, sh)
      if (key == self.last_key or type(fid) is not int or not 0 <= fid < 2**32 or
          not all(type(v) is int and 0 < v <= 2048 for v in (w, h, sw, sh)) or
          w * h > 1344 * 760 or not 0 <= packet['sent'] - frame['time'] < .3 or
          not 0 <= packet['sent'] - captured < .35 or not 0 <= now - received < .5):
        return None
      stamp = received - (packet['sent'] - captured)
      if not 0 <= now - stamp < .5:
        return None
      encoded = frame['jpeg']
      if not isinstance(encoded, str) or len(encoded) > 280000:
        return None
      raw = base64.b64decode(encoded, validate=True)
      with Image.open(BytesIO(raw)) as image:
        if image.format != 'JPEG' or image.size != (w, h):
          return None
        rgb = np.array(image.convert('RGB'))
      self.last_key = key
      return {'rgb': rgb, 'captured_mono': stamp, 'frame_id': fid, 'source_capture': captured,
              'source_width': sw, 'source_height': sh, 'resolution': [w, h]}
    except (KeyError, ValueError, TypeError, OSError, OverflowError):
      return None


def event_data(packet, name, max_age):
  """Decode only valid, source-fresh cereal events. Optional outside the live host."""
  if (not packet.get('valid', {}).get(name) or not packet.get('alive', {}).get(name) or
      not 0 <= packet['sent'] - packet.get('mono', {}).get(name, 0) / 1e9 < max_age):
    return None
  from openpilot.cereal import log
  raw = base64.b64decode(packet['events'][name], validate=True)
  with log.Event.from_bytes(raw) as event:
    return getattr(event, name).to_dict() if event.valid and event.which() == name else None


def calibration(packet, frame):
  try:
    cal = event_data(packet, 'liveCalibration', 3.)
    device = event_data(packet, 'deviceState', 3.)
    road = event_data(packet, 'roadCameraState', .5)
    if (not cal or not device or not road or cal.get('calStatus') != 'calibrated' or
        len(cal.get('rpyCalib', [])) != 3 or len(cal.get('height', [])) != 1):
      return None
    # This trial deliberately supports only the user's known C4 narrow camera.
    # Other profiles keep class/box display, without fabricated metric positions.
    if device.get('deviceType') != 'mici' or road.get('sensor') != 'os04c10':
      return None
    if (frame['source_width'], frame['source_height']) != (1344, 760):
      return None
    return {'width': 1344, 'height': 760, 'focal': 1141.5,
            'rpy': cal['rpyCalib'], 'height_m': cal['height'][0]}
  except Exception:
    return None  # Optional range estimation never prevents 2-D classification.


def write_result(path, result):
  path = Path(path)
  raw = json.dumps(result, separators=(',', ':'), allow_nan=False)
  if len(raw.encode()) > 32768:
    raise ValueError('Detection result exceeds display budget')
  temporary = path.with_suffix('.tmp')
  temporary.write_text(raw)
  temporary.replace(path)
