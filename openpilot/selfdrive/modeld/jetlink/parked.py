"""Opt-in parked App selection; never fake IsOffroad or trust stale telemetry."""
import json
import math
from pathlib import Path
import time

ENABLE = Path('/data/jetlink-parked-model-switch')
MODEL_STATUS = Path('/dev/shm/carrot-jetlink-model.json')
SERVICES = ('carState', 'selfdriveState', 'carControl')
MAX_AGE = .25
HOLD = 2.


def stationary_disabled(now, messages, valid, received, require_park=True):
  try:
    if not all(valid.get(k) is True and 0 <= now - received[k] < MAX_AGE for k in SERVICES):
      return False
    car, drive, control = (messages[k] for k in SERVICES)
    speeds = (float(car.vEgo), float(car.vEgoRaw))
    return (car.canValid is True and car.canTimeout is False and car.standstill is True
            and str(car.gearShifter) in (('park',) if require_park else ('park', 'drive'))
            and all(math.isfinite(v) and abs(v) < .01 for v in speeds)
            and drive.enabled is False and drive.active is False
            and control.enabled is False and control.latActive is False and control.longActive is False)
  except (KeyError, AttributeError, TypeError, ValueError, OverflowError):
    return False


class ParkedGate:
  def __init__(self):
    self.since = None

  def update(self, now, messages, valid, received):
    if not stationary_disabled(now, messages, valid, received):
      self.since = None
      return False
    if self.since is None or now < self.since:
      self.since = now
    return now - self.since >= HOLD


def fallback_ack(now, path=MODEL_STATUS):
  try:
    record = json.loads(path.read_text())
    age = now - float(record['updated'])
    return (0 <= age < MAX_AGE and record.get('parked_switch_ready') is True
            and record.get('active') is False)
  except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError):
    return False


class ParkedWindow:
  """Daemon checks fresh CAN/control state AND a running native-model handoff."""
  def __init__(self):
    self.sm = None
    self.gate = ParkedGate()

  def __call__(self):
    if not ENABLE.is_file():
      self.gate.since = None
      return False
    try:
      if self.sm is None:
        from openpilot.cereal.messaging import SubMaster
        self.sm = SubMaster(list(SERVICES))
      self.sm.update(0)
      now = time.monotonic()
      allowed = self.gate.update(now, {k: self.sm[k] for k in SERVICES},
                                 {k: bool(self.sm.valid[k] and self.sm.alive[k]) for k in SERVICES}, self.sm.recv_time)
      return allowed and fallback_ack(now)
    except Exception:
      self.gate.since = None
      return False
