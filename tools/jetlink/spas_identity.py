"""Bounded, parked, single-endpoint identity/DTC reads for this owner's Ioniq 5.

Default: passive preflight only. --execute --parked-ready temporarily uses the
existing pandad ELM327/1 diagnostic mode. No firmware flash, UDS session change,
communication control, actuator request, coding, DTC clearing or bus scan.
"""
import argparse
from collections import Counter
import fcntl
import json
import math
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

TARGET, RESPONSE = 0x7B1, 0x7B9
DEVICE = '99411088c9cfd064'
READS = tuple(bytes.fromhex('22' + d) for d in ('f100', 'f110', 'f187', 'f189', 'f197')) + (bytes.fromhex('1902ff'),)
KEYS = ('IsOnroad', 'FirmwareQueryDone', 'ControlsReady', 'ObdMultiplexingEnabled', 'ObdMultiplexingChanged')


def device_matches(value):
  if isinstance(value, bytes):
    try:
      value = value.decode('ascii')
    except UnicodeDecodeError:
      return False
  return isinstance(value, str) and value == DEVICE


def snapshot_parameters(params):
  # All KEYS are booleans. Read their raw representation to preserve absence,
  # rather than assuming typed Params.get() returns bytes (it returns bool).
  saved = {}
  for key in KEYS:
    try:
      raw = Path(params.get_param_path(key)).read_bytes()
    except FileNotFoundError:
      raw = None
    if raw not in (None, b'0', b'1'):
      raise RuntimeError('Unexpected boolean storage for ' + key)
    saved[key] = None if raw is None else raw.hex()
  return saved


def restore_parameter(params, key, value):
  if key not in KEYS or value not in (None, '30', '31'):
    raise ValueError('Invalid boolean restoration entry')
  if value is None:
    params.remove(key)
  else:
    params.put_bool(key, value == '31')


def emit(value):
  print(json.dumps(value, ensure_ascii=False), flush=True)


def process(pid):
  root = Path('/proc') / str(pid)
  fields = (root / 'stat').read_text().rsplit(') ', 1)[1].split()
  return {'pid': pid, 'start': fields[19], 'state': fields[0], 'parent': int(fields[1]),
          'cmd': (root / 'cmdline').read_bytes().replace(b'\x00', b' ').decode(errors='replace')}


def same_process(saved):
  try:
    return process(saved['pid'])['start'] == saved['start']
  except (FileNotFoundError, ProcessLookupError):
    return False


def send_signal(saved, sig):
  if not same_process(saved):
    raise RuntimeError('Process changed: ' + str(saved['pid']))
  os.kill(saved['pid'], sig)


def packet(payload):
  if payload not in READS:
    raise ValueError('Only fixed identity/DTC reads are permitted')
  return (bytes([len(payload)]) + payload).ljust(8, b'\x00')


class Reply:
  """One bounded ISO-TP response; FC only follows a solicited first frame."""
  def __init__(self, request):
    self.request, self.data, self.length, self.sequence = request, bytearray(), None, 1

  def feed(self, data):
    if len(data) != 8:
      raise ValueError('Unexpected response frame length')
    kind = data[0] >> 4
    if kind == 0:
      n = data[0] & 15
      if not 1 <= n <= 7 or self.length is not None:
        raise ValueError('Invalid or overlapping single frame')
      return bytes(data[1:1+n]), False
    if kind == 1:
      if self.length is not None:
        raise ValueError('Overlapping first frame')
      self.length = ((data[0] & 15) << 8) | data[1]
      if not 8 <= self.length <= 512:
        raise ValueError('Response exceeds bounded receive size')
      # Only extend the specifically requested positive response.
      prefix = bytes([self.request[0]+0x40]) + self.request[1:3 if self.request[0] == 0x22 else 2]
      if not data[2:].startswith(prefix):
        raise ValueError('First frame does not match requested service/DID')
      self.data.extend(data[2:])
      return None, True
    if kind == 2 and self.length is not None:
      if data[0] & 15 != self.sequence:
        raise ValueError('Consecutive-frame sequence mismatch')
      self.sequence = (self.sequence+1) & 15
      self.data.extend(data[1:])
      if len(self.data) >= self.length:
        return bytes(self.data[:self.length]), False
      return None, False
    raise ValueError('Unexpected ISO-TP frame')


class ParkGuard:
  def __init__(self):
    self.values = {}
    self.stats = {a: Counter() for a in (0x35, 0xA0)}
    self.latest = {}

  def observe(self, address, data, stamp):
    if address not in (0x35, 0xA0):
      return
    stats = self.stats[address]
    stats['received'] += 1
    self.latest[address] = {'length': len(data)}
    size = 32 if address == 0x35 else 24
    if len(data) != size:
      stats['wrong_length'] += 1
      self.values.pop(address, None)
      return
    crc = 0
    for byte in data[2:] + address.to_bytes(2, 'little'):
      crc ^= byte << 8
      for _ in range(8):
        crc = ((crc << 1) ^ (0x1021 if crc & 0x8000 else 0)) & 0xffff
    expected_crc = crc ^ {24: 0x819d, 32: 0x9f5b}[size]
    actual_crc = int.from_bytes(data[:2], 'little')
    self.latest[address].update(counter=data[2], crc_received=hex(actual_crc), crc_expected=hex(expected_crc))
    if actual_crc != expected_crc:
      stats['invalid_crc'] += 1
      self.values.pop(address, None)
      return
    stats['valid_crc'] += 1
    old = self.values.get(address)
    if old:
      stats['same_batch_timestamp'] += stamp == old[0]
      stats['counter_discontinuities'] += data[2] != (old[1]+1) % 256
    # logMonoTime timestamps a received batch, not each physical CAN frame.
    # Consecutive frames in one batch may share a timestamp; require advancing
    # OEM counters and a nondecreasing, fresh batch timestamp independently.
    count = min(20, old[2]+1) if old and 0 <= stamp-old[0] < .15 and data[2] == (old[1]+1) % 256 else 1
    safe = (data[24] & 7 == 0 and data[5] == 0) if address == 0x35 else all(
      int.from_bytes(data[i:i+2], 'little') & 0x3fff == 0 for i in (8, 10, 12, 14))
    self.latest[address].update(safe=safe)
    if address == 0x35:
      self.latest[address].update(raw_gear=data[24] & 7, raw_pedal=data[5])
    else:
      self.latest[address]['raw_wheels'] = [int.from_bytes(data[i:i+2], 'little') & 0x3fff for i in (8, 10, 12, 14)]
    stats['max_consecutive'] = max(stats['max_consecutive'], count)
    self.values[address] = (stamp, data[2], count, safe)

  def ready(self, now):
    return all(a in self.values and self.values[a][2] >= 10 and self.values[a][3] and
               0 <= now-self.values[a][0] < .15 for a in (0x35, 0xA0))

  def report(self, now):
    return {hex(a): {'counts': dict(self.stats[a]), 'latest': self.latest.get(a),
                     'consecutive': self.values[a][2] if a in self.values else 0,
                     'age_ms': round((now-self.values[a][0])*1000, 2) if a in self.values else None}
            for a in (0x35, 0xA0)}


def panda_health(sm, model=None, parameter=None):
  now = time.monotonic()
  if not sm.seen['pandaStates'] or not sm.valid['pandaStates'] or now-sm.recv_time['pandaStates'] > 1.:
    raise RuntimeError('Panda telemetry missing/stale')
  pandas = sm['pandaStates']
  if len(pandas) != 1:
    raise RuntimeError('Requires exactly one Panda')
  p = pandas[0]
  if p.controlsAllowed or list(p.faults) or p.safetyRxChecksInvalid or not p.ignitionLine:
    raise RuntimeError('Panda control/fault/ignition guard failed')
  if model is not None and (str(p.safetyModel) != model or p.safetyParam != parameter):
    raise RuntimeError('Unexpected safety mode')
  counts = [int(p.safetyTxBlocked)]
  for i in range(3):
    c = getattr(p, 'canState' + str(i))
    if c.busOff or c.errorWarning or c.errorPassive or c.transmitErrorCnt or c.receiveErrorCnt:
      raise RuntimeError('CAN controller unhealthy')
    counts.extend(int(getattr(c, k)) for k in ('totalErrorCnt', 'busOffCnt', 'totalTxLostCnt', 'totalRxLostCnt'))
  return tuple(counts)


class Vehicle:
  def __init__(self):
    from openpilot.cereal import messaging
    self.messaging = messaging
    self.sm = messaging.SubMaster(['carState', 'carControl', 'selfdriveState', 'pandaStates', 'managerState'])
    self.sock = messaging.sub_sock('can', conflate=False)
    self.guard, self.pub = ParkGuard(), None
    self.input_stats = Counter()

  def pump(self):
    self.sm.update(0)
    packets = []
    for msg in self.messaging.drain_sock(self.sock, wait_for_one=False):
      # drain_sock can receive batches published after this pump began.
      # Compare their source time with a clock sampled AFTER reception.
      now = time.monotonic()
      self.input_stats['batches'] += 1
      stamp = msg.logMonoTime / 1e9
      if not msg.valid or not 0 <= now-stamp < .15:
        self.input_stats['invalid_batches' if not msg.valid else 'future_batches' if stamp > now else 'stale_batches'] += 1
        continue
      for item in msg.can:
        self.input_stats['source_' + str(item.src)] += 1
        if item.src == 0:
          data = bytes(item.dat)
          self.guard.observe(item.address, data, stamp)
          packets.append((item.address, data))
    return packets

  def assert_guard(self, expected=None, baseline=None):
    if not self.guard.ready(time.monotonic()):
      raise RuntimeError('Raw CRC/counter-qualified P/zero/pedal guard failed')
    health = panda_health(self.sm, *(expected or (None, None)))
    if baseline is not None and health != baseline:
      raise RuntimeError('CAN errors/losses or safety rejections changed')
    return health

  def report(self, original):
    now, sm = time.monotonic(), self.sm
    services = {k: {'seen': sm.seen[k], 'valid': sm.valid[k],
                    'age_ms': round((now-sm.recv_time[k])*1000, 2) if sm.seen[k] else None}
                for k in ('carState', 'carControl', 'selfdriveState', 'pandaStates', 'managerState')}
    pandas = []
    for p in sm['pandaStates']:
      buses = []
      for i in range(3):
        c = getattr(p, 'canState' + str(i))
        buses.append({k: getattr(c, k) for k in ('busOff', 'errorWarning', 'errorPassive', 'transmitErrorCnt',
                      'receiveErrorCnt', 'totalErrorCnt', 'totalTxLostCnt', 'totalRxLostCnt')})
      pandas.append({'mode': str(p.safetyModel), 'param': p.safetyParam, 'controlsAllowed': p.controlsAllowed,
                     'ignitionLine': p.ignitionLine, 'safetyRxChecksInvalid': p.safetyRxChecksInvalid,
                     'faults': [str(f) for f in p.faults], 'buses': buses})
    cs, cc, ss = sm['carState'], sm['carControl'], sm['selfdriveState']
    return {'expected_safety': original, 'services': services, 'can_input': dict(self.input_stats),
            'raw_guard': self.guard.report(now), 'pandas': pandas,
            'vehicle': {'gear': str(cs.gearShifter), 'speed': cs.vEgo, 'standstill': cs.standstill,
                        'canValid': cs.canValid, 'gasPressed': cs.gasPressed,
                        'leftBlinker': cs.leftBlinker, 'rightBlinker': cs.rightBlinker,
                        'latActive': cc.latActive, 'longActive': cc.longActive, 'enabled': ss.enabled, 'active': ss.active}}

  def tx(self, data, baseline):
    if data not in tuple(packet(r) for r in READS) + (bytes.fromhex('3000050000000000'),):
      raise RuntimeError('Transmission not allowed')
    from openpilot.selfdrive.pandad import can_list_to_can_capnp
    self.pump()
    self.assert_guard(('elm327', 1), baseline)
    self.pub.send(can_list_to_can_capnp([(TARGET, data, 0)], msgtype='sendcan'))

  def query(self, request, baseline):
    self.pump()  # Discard old diagnostics before sending a different DID.
    reply = Reply(request)
    self.tx(packet(request), baseline)
    until = time.monotonic()+1.5
    while time.monotonic() < until:
      packets = self.pump()
      self.assert_guard(('elm327', 1), baseline)
      for address, data in packets:
        if address != RESPONSE:
          continue
        payload, fc = reply.feed(data)
        if fc:
          self.tx(bytes.fromhex('3000050000000000'), baseline)
        if payload is not None:
          if payload[:2] == bytes([0x7f, request[0]]) and len(payload) == 3:
            if payload[2] == 0x78:
              continue  # Fixed overall deadline; never renewed by pending.
            return {'request': request.hex(), 'status': 'negative', 'response': payload.hex(), 'nrc': hex(payload[2])}
          prefix = bytes([request[0]+0x40]) + request[1:3 if request[0] == 0x22 else 2]
          if not payload.startswith(prefix):
            raise RuntimeError('Response service/DID mismatch')
          return {'request': request.hex(), 'status': 'positive', 'response': payload.hex(),
                  'data_repr': repr(payload[len(prefix):])}
      time.sleep(.01)
    return {'request': request.hex(), 'status': 'timeout', 'meaning': 'No matching ECU response; not proof of absence'}


def preflight(v, params):
  from openpilot.cereal import car
  if not device_matches(params.get('DongleId')):
    raise RuntimeError('This diagnostic is restricted to the reviewed owner device')
  raw = params.get('CarParams')
  if not raw:
    raise RuntimeError('CarParams missing')
  with car.CarParams.from_bytes(raw) as cp:
    if cp.carFingerprint != 'HYUNDAI_IONIQ_5' or cp.passive or not cp.flags & 2048:
      raise RuntimeError('Requires the reviewed non-passive Ioniq 5 EV layout')
    original = (str(cp.safetyConfigs[-1].safetyModel), int(cp.safetyConfigs[-1].safetyParam))
  for key in ('AutoBlinkerControl', 'CanfdBlinkerTest'):
    if params.get_int(key) != 0:
      raise RuntimeError(key + ' must already be 0; this tool never changes indicator settings')
  stable, until, reasons = None, time.monotonic()+10, Counter()
  while time.monotonic() < until:
    v.pump()
    try:
      v.assert_guard(original)
      now = time.monotonic()
      for key in ('carState', 'carControl', 'selfdriveState', 'managerState'):
        if not v.sm.seen[key] or not v.sm.valid[key] or now-v.sm.recv_time[key] > 1.:
          raise RuntimeError('Normal vehicle telemetry stale/invalid: ' + key)
      cs, cc, ss = v.sm['carState'], v.sm['carControl'], v.sm['selfdriveState']
      if (not cs.canValid or str(cs.gearShifter) != 'park' or not cs.standstill or not math.isfinite(cs.vEgo) or
          abs(cs.vEgo) >= .01 or cs.gasPressed or cs.leftBlinker or cs.rightBlinker or cc.latActive or cc.longActive or ss.enabled or ss.active):
        raise RuntimeError('Vehicle is not parked/inactive/neutral')
      stable = stable or now
      if now-stable >= 3.:
        break
    except RuntimeError as exc:
      reasons[str(exc)] += 1
      stable = None
    time.sleep(.01)
  else:
    emit({'preflight_diagnostics': v.report(original), 'failure_reasons': dict(reasons),
          'vehicle_mutated': False, 'diagnostic_requests_sent': 0})
    raise RuntimeError('Three-second stable parked preflight failed')
  states = {p.name: p for p in v.sm['managerState'].processes if p.running}
  if not all(k in states for k in ('card', 'controlsd', 'pandad')):
    raise RuntimeError('Required managed process missing')
  card, controls = process(states['card'].pid), process(states['controlsd'].pid)
  manager = process(card['parent'])
  if not ('manager.py' in manager['cmd'] or 'system.manager.manager' in manager['cmd']):
    raise RuntimeError('Cannot positively identify card manager parent')
  if any(p['state'] in ('T', 't', 'Z') for p in (card, controls, manager)):
    raise RuntimeError('A required process is already stopped/dead')
  if not all(params.get_bool(key) for key in ('IsOnroad', 'FirmwareQueryDone', 'ControlsReady')):
    raise RuntimeError('Normal startup safety configuration incomplete')
  return original, {'manager': manager, 'controls': controls, 'card': card}


def wait_mode(v, model, parameter, seconds=4.):
  until = time.monotonic()+seconds
  while time.monotonic() < until:
    v.pump()
    try:
      return v.assert_guard((model, parameter))
    except RuntimeError:
      pass
    time.sleep(.02)
  raise RuntimeError('Safety mode transition not confirmed: ' + model)


def recover(snapshot, pipe_fd, ready_fd=None):
  # Independent process survives SSH/parent loss. Parent has no CAN ownership
  # through USB/SPI; pandad remains alive for all mode changes.
  from openpilot.common.params import Params
  p = Params()
  v = Vehicle() if ready_fd is not None else None
  if ready_fd is not None:
    os.write(ready_fd, b'R')  # Imports/subscriptions ready BEFORE any pause/mutation.
    os.close(ready_fd)
  ready, _, _ = select.select([pipe_fd], [], [], 35.)
  if not ready:
    if same_process(snapshot['owner']):
      os.kill(snapshot['owner']['pid'], signal.SIGKILL)
  else:
    os.read(pipe_fd, 1)  # EOF on ordinary finish, exception or parent death.
  if snapshot.get('armed_file') and not Path(snapshot['armed_file']).exists():
    Path(snapshot['result']).write_text(json.dumps({'restored': True, 'vehicle_mutated': False,
                                                   'errors': [], 'next': 'No vehicle state change was started'}))
    return
  errors = []
  # Let live pandad return to noOutput before restoring the startup handshake.
  try:
    p.put_bool('IsOnroad', False)
    time.sleep(.5)
    for key in KEYS[1:]:
      restore_parameter(p, key, snapshot['params'][key])
    restore_parameter(p, 'IsOnroad', snapshot['params']['IsOnroad'])
  except Exception as e:
    errors.append(str(e))
  for name in ('controls', 'manager'):
    try:
      send_signal(snapshot['processes'][name], signal.SIGCONT)
    except Exception as e:
      errors.append(name + ': ' + str(e))
  # Do not call restoration successful based on Params writes alone.
  restored = False
  try:
    v = v or Vehicle()
    until = time.monotonic()+12.
    while time.monotonic() < until:
      v.pump()
      now = time.monotonic()
      live = all(v.sm.seen[k] and v.sm.valid[k] and now-v.sm.recv_time[k] < 1.
                 for k in ('carState', 'carControl', 'selfdriveState', 'managerState'))
      running = {s.name for s in v.sm['managerState'].processes if s.running}
      try:
        v.assert_guard(tuple(snapshot['original']))
        cs, ss = v.sm['carState'], v.sm['selfdriveState']
        if live and {'card', 'controlsd', 'pandad'} <= running and cs.canValid and not ss.enabled and not ss.active:
          restored = True
          break
      except RuntimeError:
        pass
      time.sleep(.05)
  except Exception as e:
    errors.append(str(e))
  result = {'restored': restored, 'errors': errors,
            'next': 'Normal live safety and processes verified' if restored else 'Do not drive; keep parked and reboot C4 normally, then inspect telemetry'}
  Path(snapshot['result']).write_text(json.dumps(result))


def execute(v, params, original, processes, requests=READS):
  if not requests or any(request not in READS for request in requests):
    raise ValueError('Only fixed identity/DTC reads are permitted')
  import tempfile
  work = Path(tempfile.mkdtemp(prefix='spas-identity-', dir='/data'))
  os.chmod(work, 0o700)
  snapshot = {'owner': process(os.getpid()), 'original': original, 'processes': processes,
              'params': snapshot_parameters(params),
              'armed_file': str(work / 'mutation_started'),
              'result': str(work / 'restoration.json')}
  state = work / 'recovery.json'
  state.write_text(json.dumps(snapshot))
  read_fd, write_fd = os.pipe()
  ready_read, ready_write = os.pipe()
  log = (work / 'recovery.log').open('w')
  watch = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--recover', str(state), str(read_fd), str(ready_write)],
                           pass_fds=(read_fd, ready_write), stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
  os.close(read_fd)
  os.close(ready_write)
  results, active_request, phase = [], None, 'recovery_startup'
  try:
    until = time.monotonic()+5.
    while True:
      v.pump()  # Native imports in the recovery child must not age our CAN queue.
      ready, _, _ = select.select([ready_read], [], [], .02)
      if ready:
        if os.read(ready_read, 1) != b'R' or watch.poll() is not None:
          raise RuntimeError('Recovery process did not become ready; vehicle untouched')
        break
      if time.monotonic() >= until or watch.poll() is not None:
        raise RuntimeError('Recovery process did not become ready; vehicle untouched')
    emit({'recovery_directory': str(work), 'diagnostic_target': hex(TARGET), 'bus': 0})
    phase = 'revalidate_before_pause'
    current_safety, current_processes = preflight(v, params)
    if current_safety != original or any(current_processes[k]['pid'] != processes[k]['pid'] or
                                         current_processes[k]['start'] != processes[k]['start'] for k in processes):
      raise RuntimeError('Vehicle safety/process identity changed before pause')
    Path(snapshot['armed_file']).touch()
    phase = 'pause_normal_sender'
    send_signal(processes['manager'], signal.SIGSTOP)
    send_signal(processes['controls'], signal.SIGSTOP)
    send_signal(processes['card'], signal.SIGINT)
    until = time.monotonic()+4.
    while same_process(processes['card']) and process(processes['card']['pid'])['state'] != 'Z':
      v.pump()
      v.assert_guard()
      if time.monotonic() >= until:
        raise RuntimeError('card did not exit; no diagnostic mode requested')
      time.sleep(.02)
    # Register restoration before touching the startup handshake. Keep pandad.
    params.put_bool('IsOnroad', False)
    phase = 'wait_no_output'
    wait_mode(v, 'noOutput', 0)
    params.put_bool('FirmwareQueryDone', False)
    params.put_bool('ControlsReady', False)
    params.put_bool('ObdMultiplexingEnabled', False)
    params.put_bool('IsOnroad', True)
    phase = 'wait_diagnostic_mode'
    baseline = wait_mode(v, 'elm327', 1)
    v.pub = v.messaging.pub_sock('sendcan')
    phase = 'publisher_startup'
    until = time.monotonic()+.15
    while time.monotonic() < until:
      v.pump()
      v.assert_guard(('elm327', 1), baseline)
      time.sleep(.01)
    for request in requests:
      phase, active_request = 'read', request.hex()
      result = v.query(request, baseline)
      results.append(result)
      emit(result)
      (work / 'reads.json').write_text(json.dumps(results, indent=2))
      phase, active_request = 'between_reads', None
      if request == requests[-1]:
        break  # Restore immediately after the last bounded response.
      until = time.monotonic()+.1
      while time.monotonic() < until:
        v.pump()
        v.assert_guard(('elm327', 1), baseline)
        time.sleep(.01)
    (work / 'reads.json').write_text(json.dumps(results, indent=2))
  except BaseException as exc:
    # Capture before recovery changes the mode and before paused telemetry is
    # refreshed. Stale normal services are expected during this diagnostic;
    # raw park inputs and live pandad telemetry remain the active guards.
    failure = {'diagnostic_stopped': str(exc), 'phase': phase, 'active_request': active_request,
               'completed_reads': results, 'context': v.report(('elm327', 1))}
    emit(failure)
    (work / 'failure.json').write_text(json.dumps(failure, indent=2))
    raise
  finally:
    if v.pub is not None:
      del v.pub
      v.pub = None
    os.close(ready_read)
    os.close(write_fd)  # Independent recovery owns restoration on all exits.
    try:
      watch.wait(timeout=20.)
    except subprocess.TimeoutExpired as exc:
      # Never kill the independent restorer or report success from a timeout.
      raise RuntimeError('Recovery still running: keep parked; inspect ' + str(work)) from exc
    log.close()
    path = Path(snapshot['result'])
    result = json.loads(path.read_text()) if path.exists() else {'restored': False, 'error': 'Recovery report missing', 'directory': str(work)}
    emit(result)
    if not result['restored']:
      raise RuntimeError('Restoration not confirmed; keep parked, reboot C4 normally and inspect telemetry')


def main():
  if len(sys.argv) == 5 and sys.argv[1] == '--recover':
    recover(json.loads(Path(sys.argv[2]).read_text()), int(sys.argv[3]), int(sys.argv[4]))
    return 0
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--check', action='store_true', help='Passive preflight only (default)')
  parser.add_argument('--execute', action='store_true', help='Run fixed identity/DTC reads after guarded temporary diagnostic-mode transition')
  parser.add_argument('--parked-ready', action='store_true', help='Operator confirms P, parking brake, READY and no driving during this procedure')
  parser.add_argument('--dtc-only', action='store_true', help='Read only DTC status (1902ff); skip identity requests already obtained')
  args = parser.parse_args()
  if args.check and args.execute:
    parser.error('--check and --execute are mutually exclusive')
  if args.execute and not args.parked_ready:
    parser.error('--execute requires --parked-ready')
  from openpilot.common.params import Params
  with open('/tmp/carrot-spas-identity.lock', 'a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    v, params = Vehicle(), Params()
    original, processes = preflight(v, params)
    requests = (READS[-1],) if args.dtc_only else READS
    emit({'preflight': True, 'original_safety': original, 'queries': [r.hex() for r in requests],
          'execute': args.execute, 'vehicle_validation': 'NOT YET PERFORMED'})
    if args.execute:
      execute(v, params, original, processes, requests)
  return 0


if __name__ == '__main__':
  def interrupted(signum, frame):
    raise KeyboardInterrupt('Signal ' + str(signum))
  for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
    signal.signal(sig, interrupted)
  try:
    raise SystemExit(main())
  except (Exception, KeyboardInterrupt) as exc:
    emit({'stopped': str(exc)})
    raise SystemExit(2)
