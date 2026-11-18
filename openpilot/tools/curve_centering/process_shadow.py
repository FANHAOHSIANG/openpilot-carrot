"""Isolated observer with caller-controlled startup. Control-side work is one fixed 128-byte datagram.

No geometry traversal, whole-message serialization, analysis thread, blocking send or join in
observe(). Child subscribes to model/plan and requires exact consumed timestamps.
No return channel can select an actuator command. This is not C4 qualification.
"""
import multiprocessing
import socket
import struct
import time

WIRE = struct.Struct('<4s7QI8d')
MAGIC = b'CS01'
NAMES = ('lat_active', 'driver_steering', 'driver_gas', 'driver_brake', 'left', 'right',
         'maneuver', 'saturated', 'saturation_known', 'safety_limited', 'messages_valid',
         'lane_mode', 'vw_meb', 'lateral_started', 'lac_active')


def decode(raw):
  if len(raw) != WIRE.size:
    raise ValueError('packet size')
  magic, generation, sequence, now, model, plan, cs, params, flags, *values = WIRE.unpack(raw)
  if magic != MAGIC or flags >> len(NAMES):
    raise ValueError('packet version or flags')
  return {'generation': generation, 'sequence': sequence, 'now': now, 'model': model,
          'plan': plan, 'cs': cs, 'params': params, 'flags': dict(zip(NAMES, (bool(flags & (1 << i)) for i in range(len(NAMES))), strict=True)),
          'values': values}


class ExactJoin:
  """Bounded child-only cache. A missing exact source never falls back to latest."""
  def __init__(self):
    from .runtime_shadow import ShadowProcessor
    self.processor = ShadowProcessor()
    self.cache = {'modelV2': {}, 'lateralPlan': {}}
    self.previous = None
    self.generation = 0
    self.seen = {}

  def add(self, name, ns, valid, data):
    cache = self.cache[name]
    if ns in cache and cache[ns][1] != data:
      cache[ns] = (False, cache[ns][1])
    else:
      cache[ns] = (valid and cache.get(ns, (True, None))[0], data)
    while len(cache) > 64:
      del cache[next(iter(cache))]

  def reset(self):
    self.generation += 1
    self.seen.clear()

  def process(self, packet):
    from .control_bridge import ControlTick
    from .runtime_shadow import Capture
    p, f = packet, packet['flags']
    if self.previous is not None and (p['generation'] != self.previous['generation'] or p['sequence'] != self.previous['sequence']+1):
      self.reset()
    self.previous = p
    if p['model'] not in self.cache['modelV2'] or p['plan'] not in self.cache['lateralPlan']:
      self.reset()
      return {'reasons': ['missing_exact_source'], 'vehicle_output': False}
    model_valid, model = self.cache['modelV2'][p['model']]
    plan_valid, plan = self.cache['lateralPlan'][p['plan']]
    if plan['modelMonoTime'] != p['model']:
      self.reset()
      return {'reasons': ['mismatched_consumed_plan'], 'vehicle_output': False}
    action, speed, feedback, roll, previous, actual, actual_accel, desired_accel = p['values']
    tick = ControlTick(p['now'], p['model'], p['cs'], p['params'], action, speed, feedback, roll,
                       f['lat_active'], f['driver_steering'], f['driver_gas'], f['driver_brake'], f['maneuver'],
                       f['saturated'] if f['saturation_known'] else None, f['safety_limited'],
                       f['messages_valid'] and model_valid and plan_valid, f['lane_mode'], 1., 0., f['vw_meb'])
    records = [{'kind': 'carState', 'mono_ns': p['cs'], 't': p['cs']/1e9, 'valid': f['messages_valid'],
                'data': {'vEgo': speed, 'steeringPressed': f['driver_steering'], 'gasPressed': f['driver_gas'],
                         'brakePressed': f['driver_brake'], 'leftBlinker': f['left'], 'rightBlinker': f['right']}}]
    for name, ns, valid, data in (('modelV2', p['model'], model_valid, model), ('lateralPlan', p['plan'], plan_valid, plan)):
      if self.seen.get(name) != ns:
        records.append({'kind': name, 'mono_ns': ns, 't': ns/1e9, 'valid': valid, 'data': data})
        self.seen[name] = ns
    records.extend([
      {'kind': 'carControl', 'mono_ns': p['now'], 't': p['now']/1e9, 'valid': True,
       'data': {'latActive': f['lat_active'], 'actuators': {'curvature': actual}}},
      {'kind': 'controlsState', 'mono_ns': p['now'], 't': p['now']/1e9, 'valid': True,
       'data': {'curvature': feedback, 'lateralControlState': {'torqueState': {
         'saturated': f['saturated'] if f['saturation_known'] else None, 'active': f['lac_active'],
         'actualLateralAccel': actual_accel, 'desiredLateralAccel': desired_accel}}}},
    ])
    return self.processor.process(Capture(tick, tuple(records), previous, f['lateral_started'], actual, self.generation))


def worker_main(channel, hook=None, sink=None):
  """All native IPC, source geometry and policy work stays in this process."""
  import select
  import openpilot.cereal.messaging as messaging
  from openpilot.common.swaglog import cloudlog
  from .runtime_shadow import snapshot
  sockets = {name: messaging.sub_sock(name, conflate=False, timeout=0) for name in ('modelV2', 'lateralPlan')}
  join = ExactJoin()
  last_packet = time.monotonic()
  last_emit = 0
  def refresh_sources():
    for name, sock in sockets.items():
      for _ in range(32):
        msg = messaging.recv_one_or_none(sock)
        if msg is None:
          break
        try:
          data = snapshot(name, getattr(msg, name))
        except (ValueError, AttributeError):
          join.cache[name].pop(msg.logMonoTime, None)
          continue
        join.add(name, msg.logMonoTime, msg.valid, data)

  try:
    while time.monotonic()-last_packet < 2.:
      refresh_sources()
      if not select.select([channel], [], [], .005)[0]:
        continue
      raw = None
      for _ in range(8):
        try:
          raw = channel.recv(WIRE.size+1)
        except BlockingIOError:
          break
      if raw is None:
        continue
      refresh_sources()  # sources may have arrived while waiting for the control datagram
      p = decode(raw)
      last_packet = time.monotonic()
      if not 0 <= time.monotonic_ns()-p['now'] <= 200_000_000:
        join.reset()
        continue
      started, cpu = time.monotonic_ns(), time.thread_time_ns()
      if hook is not None:
        hook(p)
      result = join.process(p)
      observation_age = time.monotonic_ns()-p['now']
      if observation_age > 200_000_000:
        join.reset()
        result = {'reasons': ['processing_deadline_expired']}
      report = {'mode': 'process_shadow_only', 'vehicle_output': False, 'sequence': p['sequence'],
                'generation': join.generation, 'now_ns': p['now'], 'observation_age_ns': observation_age, 'reasons': result['reasons'],
                'actual_baseline_error': result.get('actual_baseline_error'),
                'policy_delta_curvature': result.get('policy_delta_curvature'),
                'history_delta_curvature': result.get('residual_curvature'),
                'worker_wall_ns': time.monotonic_ns()-started, 'worker_cpu_ns': time.thread_time_ns()-cpu}
      if sink is not None:
        sink(report)
      if p['now']-last_emit >= 1_000_000_000:
        cloudlog.event('curve_centering_shadow', **report)
        last_emit = p['now']
  except Exception:
    cloudlog.exception('curve_centering_shadow_worker_failed')
  finally:
    channel.close()


class ProcessShadow:
  def __init__(self, *, start_worker=True, clock=time.monotonic_ns, worker_hook=None, worker_sink=None):
    self.clock = clock
    self.created_ns = clock()
    self.failed = False
    self.failure_reason = None
    self.closed = False
    self.dropped = 0
    self.generation = 0
    self.sequence = 0
    self.max_capture_ns = 0
    self.full_since = None
    self.channel, receiver = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
    self.channel.setblocking(False)
    receiver.setblocking(False)
    self.channel.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024)
    self.worker = None
    self.test_receiver = None
    if start_worker:
      try:
        self.worker = multiprocessing.get_context('spawn').Process(
          target=worker_main, args=(receiver, worker_hook, worker_sink), name='curve-shadow-isolated', daemon=True)
        self.worker.start()
      except Exception:
        receiver.close()
        self.close()
        raise
      receiver.close()
    else:
      self.test_receiver = receiver

  def close(self):
    if self.closed:
      return
    self.closed = True
    self.channel.close()
    if self.test_receiver is not None:
      self.test_receiver.close()
    if self.worker is not None:
      try:
        self.worker.terminate()  # signal only; no join in the control path
      except (OSError, ValueError, AttributeError):
        pass

  def observe(self, sm, cc, lac_log, *, feedback, roll, previous, lateral_started, lane_mode, vw_meb, safety_limited):
    if self.closed or self.failed:
      return
    started = self.clock()
    try:
      cs, model = sm['carState'], sm['modelV2']
      saturated = getattr(lac_log, 'saturated', None)
      flags = (bool(cc.latActive), bool(cs.steeringPressed), bool(cs.gasPressed), bool(cs.brakePressed),
               bool(cs.leftBlinker), bool(cs.rightBlinker),
               bool(cs.leftBlinker or cs.rightBlinker or str(model.meta.laneChangeState) != 'off' or str(model.meta.desire) != 'none'),
               saturated is True, type(saturated) is bool, safety_limited,
               all(sm.seen[k] and sm.valid[k] and sm.alive[k] for k in ('modelV2', 'carState', 'liveParameters', 'lateralPlan'))
               and all(getattr(sm['liveParameters'], k, False) is True for k in ('valid', 'sensorValid', 'posenetValid')),
               lane_mode, vw_meb, lateral_started, getattr(lac_log, 'active', None) is True)
      if any(type(f) is not bool for f in flags):
        raise ValueError('invalid flags')
      self.sequence += 1
      data = WIRE.pack(MAGIC, self.generation, self.sequence, started, int(sm.logMonoTime['modelV2']),
                       int(sm.logMonoTime['lateralPlan']), int(sm.logMonoTime['carState']), int(sm.logMonoTime['liveParameters']),
                       sum(int(f) << i for i, f in enumerate(flags)), float(model.action.desiredCurvature), float(cs.vEgo),
                       float(feedback), float(roll), float(previous), float(cc.actuators.curvature),
                       float(getattr(lac_log, 'actualLateralAccel', float('nan'))),
                       float(getattr(lac_log, 'desiredLateralAccel', float('nan'))))
      try:
        self.channel.send(data)
        self.full_since = None
      except BlockingIOError:
        self.dropped += 1
        self.generation += 1
        if self.full_since is None:
          self.full_since = started
        if started-self.created_ns > 2_000_000_000 and started-self.full_since >= 200_000_000:
          raise TimeoutError('observer backpressure') from None
      self.max_capture_ns = max(self.max_capture_ns, self.clock()-started)
    except Exception as exc:
      self.failed = True
      self.failure_reason = 'transport_' + type(exc).__name__
      self.close()
