"""Read-only SPAS preflight and optional existing three-second parked test.

Run on comma: python -m tools.jetlink.spas_check [--test left|right].
No raw CAN publisher, firmware override or automatic setting activation.
"""
import argparse
import json
import math
import time
from collections import Counter


class Monitor:
  def __init__(self, bus, checksum):
    self.bus, self.checksum = bus, checksum
    self.stock = {}
    self.counts = Counter()
    self.replies = []
    self.driver = None

  def observe(self, address, data, bus, stamp, now):
    if bus != self.bus or not 0 <= now-stamp < .1:
      return
    if address in (0x165, 0x16A):
      size = 24 if address == 0x165 else 32
      old = self.stock.get(address)
      valid = len(data) == size and int.from_bytes(data[:2], 'little') == self.checksum(address, data)
      count = (old[2]+1 if old and 0 < stamp-old[0] < .1 and data[2] == (old[1]+1) % 256 else 1) if valid else 0
      self.stock[address] = (stamp, data[2] if valid else -1, count, bytes(data))
      self.counts[f'{address:#x}_valid' if valid else f'{address:#x}_invalid'] += 1
    elif address == 0x3C1 and len(data) == 8:
      crc = 0
      for byte in data[1:]:
        crc ^= byte
        for _ in range(8):
          crc = ((crc << 1) ^ (0x1d if crc & 0x80 else 0)) & 255
      if data[0] == crc ^ 0x65:
        old = self.driver
        count = old[2]+1 if old and 0 < stamp-old[0] < .5 else 1
        self.driver = (stamp, bool(data[3] & 0x40 or data[4] & 0x51), count)
      else:
        self.driver = None
    elif address == 0x7B9 and len(data) == 8 and 2 <= data[0] <= 7:
      self.replies.append((stamp, bytes(data[1:1+data[0]]).hex()))
      self.replies = self.replies[-32:]

  def ready(self, now):
    return all(a in self.stock and self.stock[a][2] >= 10 and 0 <= now-self.stock[a][0] < .1 for a in (0x165, 0x16A))

  def neutral(self, now):
    return (self.ready(now) and self.stock[0x16A][3][16] >> 5 == 0 and self.driver is not None and
            self.driver[2] >= 3 and not self.driver[1] and 0 <= now-self.driver[0] < .5)


def health(pandas):
  result = []
  if not pandas:
    return None
  for panda in pandas:
    if panda.controlsAllowed:
      return None
    result.append(int(panda.safetyTxBlocked))
    for i in range(3):
      c = getattr(panda, f'canState{i}', None)
      if c is None or c.busOff or c.errorWarning or c.errorPassive:
        return None
      result.extend(int(getattr(c, k)) for k in ('totalErrorCnt', 'busOffCnt', 'totalTxLostCnt', 'totalRxLostCnt'))
  return tuple(result)


def parked(sm, now):
  for k in ('carState', 'carControl', 'selfdriveState', 'pandaStates'):
    if not sm.valid[k] or not sm.alive[k] or not 0 <= now-sm.recv_time[k] < (.75 if k == 'pandaStates' else .35):
      return False
  cs, cc, ss = sm['carState'], sm['carControl'], sm['selfdriveState']
  return (cs.canValid and math.isfinite(cs.vEgo) and abs(cs.vEgo) < .01 and cs.standstill and
          str(cs.gearShifter) == 'park' and not (cs.gasPressed or cs.brakePressed or cs.blinkerLever or
          cc.latActive or cc.longActive or ss.enabled or ss.active) and health(sm['pandaStates']) is not None)


def run(args):
  # Lazy native imports allow --help and pure monitor tests on a desktop.
  from openpilot.cereal import car, messaging
  from openpilot.common.params import Params
  from opendbc.car.hyundai.hyundaicanfd import CanBus
  from opendbc.car.hyundai.spas import checksum
  from opendbc.car.hyundai.values import HyundaiFlags, HyundaiSafetyFlags
  params = Params()
  raw = params.get('CarParams')
  if raw is None:
    raise RuntimeError('CarParams missing; start the normal vehicle session first')
  with car.CarParams.from_bytes(raw) as cp:
    if cp.brand != 'hyundai' or not cp.flags & HyundaiFlags.CANFD or cp.passive:
      raise RuntimeError('Requires a non-passive Hyundai/Kia/Genesis CAN-FD session')
    bus, fingerprint = CanBus(cp).ECAN, cp.carFingerprint
    selected = bool(cp.flags & HyundaiFlags.CANFD_SPAS_BLINKERS)
  monitor = Monitor(bus, checksum)
  sm = messaging.SubMaster(['carState', 'carControl', 'selfdriveState', 'pandaStates'])
  sock = messaging.sub_sock('can', conflate=False)
  def sample():
    sm.update(0)
    now = time.monotonic()
    for msg in messaging.drain_sock(sock, wait_for_one=False):
      if msg.valid:
        for c in msg.can:
          monitor.observe(c.address, bytes(c.dat), c.src, msg.logMonoTime/1e9, now)
    return now
  print(f'Fingerprint={fingerprint}; ECAN={bus}; SPAS selected={selected}', flush=True)
  baseline, since, ready = None, None, False
  deadline = time.monotonic()+12.
  while time.monotonic() < deadline:
    now = sample()
    current = health(sm['pandaStates']) if parked(sm, now) else None
    if current is not None and monitor.neutral(now) and not (sm['carState'].leftBlinker or sm['carState'].rightBlinker):
      if current != baseline:
        baseline, since = current, now
      if since is not None and now-since >= 3.:
        ready = True
        break
    else:
      baseline, since = None, None
    time.sleep(.02)
  print(json.dumps({'parked_preflight': ready, 'stock_counts': dict(monitor.counts),
                    'ecu_handoff': 'NOT TESTED', 'lamp_operation': 'NOT TESTED'}), flush=True)
  if not args.test:
    return 0 if ready else 2
  if not ready:
    raise RuntimeError('Preflight failed; no test requested')
  if not selected or not params.get_bool('CanfdBlinkerControl'):
    raise RuntimeError('Select existing CAN-FD SPAS option and reboot normally before a test')
  if params.get_int('AutoBlinkerControl') != 0 or params.get_int('CanfdBlinkerTest') != 0:
    raise RuntimeError('Set automatic indicator mode and existing parked test to 0 before this isolated test')
  safety = sm['pandaStates'][-1]
  if str(safety.safetyModel) != 'hyundaiCanfd' or not safety.safetyParam & HyundaiSafetyFlags.CANFD_SPAS_BLINKERS:
    raise RuntimeError('Live Panda SPAS selection does not match CarParams; no test requested')
  start = time.monotonic()
  expected = 1 if args.test == 'left' else 2
  lamp_on, opposite, aborted = False, False, None
  original_stalks = (sm['carState'].leftBlinkerStalkCount, sm['carState'].rightBlinkerStalkCount)
  try:
    # Only the existing acknowledged three-second test; never direct modes 3..18.
    params.put_int('CanfdBlinkerTest', expected)
    while time.monotonic()-start < 3.5:
      now = sample()
      cs = sm['carState']
      if (not parked(sm, now) or health(sm['pandaStates']) != baseline or
          (cs.leftBlinkerStalkCount, cs.rightBlinkerStalkCount) != original_stalks or
          params.get_int('CanfdBlinkerTest') != expected or params.get_int('AutoBlinkerControl') != 0 or
          not params.get_bool('CanfdBlinkerControl')):
        aborted = 'guard_or_setting_changed'
        break
      lamp_on |= bool(cs.leftBlinker if args.test == 'left' else cs.rightBlinker)
      opposite |= bool(cs.rightBlinker if args.test == 'left' else cs.leftBlinker)
      if opposite:
        aborted = 'opposite_lamp'
        break
      time.sleep(.02)
  finally:
    params.put_int('CanfdBlinkerTest', 0)
  restored = False
  recovery_until = time.monotonic()+5.
  # Read-only recovery observation; no retry or second actuation.
  while time.monotonic() < recovery_until:
    now = sample()
    replies = [v for stamp, v in monitor.replies if stamp >= start]
    restore_ack = any(v.startswith(('6800', '5001')) for v in replies)
    if (restore_ack and parked(sm, now) and monitor.neutral(now) and
        health(sm['pandaStates']) == baseline and
        not (sm['carState'].leftBlinker or sm['carState'].rightBlinker)):
      restored = True
      break
    time.sleep(.02)
  replies = [v for stamp, v in monitor.replies if stamp >= start]
  handoff = any(v.startswith('5003') for v in replies) and any(v.startswith('6803') for v in replies)
  print(json.dumps({'direction': args.test, 'aborted': aborted, 'ecu_handoff_ack': handoff,
                    'lamp_feedback_seen': lamp_on, 'opposite_lamp_seen': opposite,
                    'restore_ack_and_stock_seen': restored, 'ecu_replies': replies,
                    'physical_visual_confirmation': 'REQUIRED', 'road_validation': 'NOT TESTED'}), flush=True)
  return 0 if handoff and lamp_on and restored and not opposite and aborted is None else 2


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--test', choices=('left', 'right'), help='explicitly request existing 3-second parked test')
  args = parser.parse_args()
  try:
    if args.test:
      import fcntl
      with open('/tmp/carrot-spas-check.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return run(args)
    return run(args)
  except (RuntimeError, OSError, ValueError) as exc:
    print(f'STOP: {exc}', flush=True)
    return 2


if __name__ == '__main__':
  raise SystemExit(main())
