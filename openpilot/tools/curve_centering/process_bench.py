"""Desktop synthetic full-controlsd process experiment; no vehicle daemons."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import threading
import time

SERVICES = [
  'liveDelay',
  'liveParameters',
  'liveTorqueParameters',
  'modelV2',
  'selfdriveState',
  'liveCalibration',
  'livePose',
  'longitudinalPlan',
  'carState',
  'carOutput',
  'carrotMan',
  'lateralPlan',
  'radarState',
  'driverMonitoringState',
  'onroadEvents',
  'driverAssistance',
]


def phase(t):
  if t < 6:
    return 'warmup'
  if t < 12:
    return 'nominal'
  if t < 16:
    return 'gil_load'
  if t < 20:
    return 'after_gil'
  if t < 24:
    return 'slow_worker'
  if t < 28:
    return 'after_overflow'
  if t < 32:
    return 'closed'
  if t < 36:
    return 'recreated'
  return 'worker_exception'


class WorkerLoad:
  def __init__(self, epoch, location, event_path, stall_s=.06):
    self.epoch, self.location, self.event_path = epoch, location, event_path
    self.stall_s = stall_s

  def __call__(self, packet):
    t = (time.monotonic_ns() - self.epoch.value) / 1e9
    current = phase(t)
    if current == 'worker_exception':
      with open(self.event_path, 'a') as f:
        f.write(json.dumps({'event': 'injected_worker_exception', 'at': t}) + '\n')
      raise RuntimeError('synthetic worker failure')
    if current == 'slow_worker':
      time.sleep(self.stall_s)
    if current == 'gil_load' and self.location == 'worker':
      end = time.monotonic() + 0.03
      x = 1
      while time.monotonic() < end:
        x = (x * 17 + 23) % 10000019


class WorkerSink:
  def __init__(self, path):
    self.path = path

  def __call__(self, result):
    with open(self.path, 'a') as f:
      f.write(json.dumps(result, allow_nan=False) + '\n')


def child(output, seconds):
  import multiprocessing
  from openpilot.selfdrive.controls import controlsd
  from openpilot.tools.curve_centering.runtime_shadow import RuntimeShadow, ShadowProcessor
  from openpilot.tools.curve_centering.process_shadow import ProcessShadow

  backend = os.environ.get('CURVE_BENCH_BACKEND', 'process')
  location = os.environ.get('CURVE_BENCH_LOAD', 'worker')
  publications, captures, diagnostics, events = [], [], [], []
  epoch = multiprocessing.get_context('spawn').RawValue('q', 0)
  origin = [None]
  stop_load = threading.Event()
  monitors = []
  worker_path, event_path = output / 'worker.jsonl', output / 'events.jsonl'
  hook = WorkerLoad(epoch, location, str(event_path), float(os.environ.get('CURVE_BENCH_STALL', '.06')))
  sink = WorkerSink(str(worker_path))

  def elapsed():
    return 0.0 if origin[0] is None else time.monotonic() - origin[0]

  def execution(m):
    return getattr(m, 'worker', None) or getattr(m, 'thread', None)

  def load():
    while not stop_load.is_set():
      if phase(elapsed()) == 'gil_load':
        end = time.monotonic() + 0.02
        x = 1
        while time.monotonic() < end:
          x = (x * 17 + 23) % 10000019
      else:
        stop_load.wait(0.002)

  if location == 'control':
    threading.Thread(target=load, daemon=True).start()
  original_observe = {RuntimeShadow: RuntimeShadow.observe, ProcessShadow: ProcessShadow.observe}
  original_process = ShadowProcessor.process

  def factory():
    if backend == 'process':
      monitor = ProcessShadow(worker_hook=hook, worker_sink=sink)
    else:

      def emit(result):
        diagnostics.append({'at': elapsed(), **result})
        controlsd.cloudlog.event('curve_centering_shadow', **result)

      monitor = RuntimeShadow(emit)
    monitors.append(monitor)
    return monitor

  def instrument_observe(self, *a, **kw):
    t, c = time.monotonic_ns(), time.thread_time_ns()
    original_observe[type(self)](self, *a, **kw)
    captures.append(
      {
        'at': elapsed(),
        'wall_ns': time.monotonic_ns() - t,
        'cpu_ns': time.thread_time_ns() - c,
        'dropped': self.dropped,
        'closed': self.closed if isinstance(self, ProcessShadow) else self._stop.is_set(),
      }
    )

  def instrument_process(self, capture):
    t, c = time.monotonic_ns(), time.thread_time_ns()
    hook({'now': capture.tick.now_ns})
    result = original_process(self, capture)
    sink(
      {
        'now_ns': capture.tick.now_ns,
        'worker_wall_ns': time.monotonic_ns() - t,
        'worker_cpu_ns': time.thread_time_ns() - c,
        'generation': capture.generation,
        'policy_delta_curvature': result['policy_delta_curvature'],
        'reasons': result['reasons'],
        'actual_baseline_error': result.get('actual_baseline_error'),
      }
    )
    return result

  RuntimeShadow.observe = instrument_observe
  ProcessShadow.observe = instrument_observe
  ShadowProcessor.process = instrument_process
  from openpilot.tools.curve_centering import process_shadow as process_module
  process_module.ProcessShadow = factory
  original_init = controlsd.Controls.__init__
  publish = controlsd.Controls.publish
  state = controlsd.Controls.state_control
  state_measure = {}

  def init_control(self):
    original_init(self)
    origin[0] = time.monotonic()
    epoch.value = int(origin[0] * 1e9)
    send = self.pm.send

    def observed_send(service, dat):
      if service == 'carControl':
        state_measure['message_ns'] = dat.logMonoTime
      return send(service, dat)

    self.pm.send = observed_send
    (output / 'ready').touch()

  def measured_state(self):
    t, c = time.monotonic_ns(), time.thread_time_ns()
    result = state(self)
    state_measure.update(state_wall_ns=time.monotonic_ns() - t, state_cpu_ns=time.thread_time_ns() - c)
    return result

  class Done(Exception):
    pass

  flags = set()

  def measured_publish(self, cc, lac):
    publish(self, cc, lac)
    t = elapsed()
    monitor = getattr(self, 'curve_shadow', None)
    publications.append(
      {
        'at': t,
        'publish_end_ns': time.monotonic_ns(),
        'input_ns': self.sm.logMonoTime['selfdriveState'],
        'lat_active': cc.latActive,
        'torque': cc.actuators.torque,
        'curvature': cc.actuators.curvature,
        'monitor_present': monitor is not None,
        'monitor_failed': bool(monitor and monitor.failed),
        'thread_alive': bool(monitor and execution(monitor) and execution(monitor).is_alive()),
        'dropped': monitor.dropped if monitor else 0,
        **state_measure,
      }
    )
    if t >= 28 and 'closed' not in flags:
      flags.add('closed')
      if monitor:
        before = time.monotonic_ns()
        monitor.close()
        events.append({'event': 'close_called', 'at': elapsed(), 'wall_ns': time.monotonic_ns() - before})
    if t >= 32 and 'recreated' not in flags:
      flags.add('recreated')
      if os.getenv('CURVE_CENTERING_SHADOW', '1') == '1':
        events.append({'event': 'recreate_called', 'at': elapsed()})
        self.curve_shadow = factory()
    if t >= seconds:
      raise Done()

  controlsd.Controls.__init__ = init_control
  controlsd.Controls.state_control = measured_state
  controlsd.Controls.publish = measured_publish
  try:
    controlsd.main()
  except Done:
    pass
  finally:
    stop_load.set()
    for m in monitors:
      m.close()
    for m in monitors:
      if execution(m):
        execution(m).join(timeout=1)
    work, parse_failures = [], 0
    if worker_path.exists():
      for line in worker_path.read_text().splitlines():
        try:
          r = json.loads(line)
          work.append(
            {
              'at': (r['now_ns'] - epoch.value) / 1e9,
              'wall_ns': r['worker_wall_ns'],
              'cpu_ns': r['worker_cpu_ns'],
              'generation': r['generation'],
              'policy_delta': r['policy_delta_curvature'],
              'reasons': r['reasons'],
              'actual_baseline_error': r.get('actual_baseline_error'), 'age_ns': r.get('observation_age_ns'),
            }
          )
        except (ValueError, KeyError):
          parse_failures += 1
    if event_path.exists():
      events.extend(json.loads(line) for line in event_path.read_text().splitlines())
    (output / 'child.json').write_text(
      json.dumps(
        {
          'backend': backend,
          'load_location': location,
          'publications': publications,
          'captures': captures,
          'worker': work,
          'diagnostics': diagnostics,
          'worker_stopped': [not execution(m).is_alive() for m in monitors],
          'worker_failures': [m.failure_reason for m in monitors],
          'events': events,
          'partial_worker_reports': parse_failures,
        }
      )
    )


def parent(output, seconds, mode):
  import openpilot.cereal.messaging as messaging
  from openpilot.common.params import Params
  from opendbc.car.car_helpers import get_demo_car_params
  from openpilot.tools.curve_centering.bridge_demo import synthetic_records
  from openpilot.cereal.services import SERVICE_LIST

  cp = get_demo_car_params()
  cp.steerActuatorDelay = 0.1
  tune = cp.lateralTuning.init('torque')
  tune.kp = 1.0
  tune.ki = 0.1
  tune.kf = 1.0
  tune.latAccelFactor = 2.963873863
  tune.friction = 0.07813665
  tune.useSteeringAngle = True
  params = Params()
  params.put('CarParams', cp.to_bytes())
  params.put_int('SteerRatioRate', 100)
  params.put_int('LatSuspendAngleDeg', 90)
  pm = messaging.PubMaster(SERVICES)
  sock = messaging.sub_sock('carControl', conflate=False, timeout=0)
  env = dict(os.environ)
  if mode == 'default':
    env.pop('CURVE_CENTERING_SHADOW', None)
  else:
    env['CURVE_CENTERING_SHADOW'] = '1' if mode == 'on' else '0'
  with (output / 'stderr.txt').open('w') as err:
    proc = subprocess.Popen([sys.executable, __file__, '--child', '--output', str(output), '--seconds', str(seconds)], env=env, stdout=err, stderr=err)
    start = time.monotonic()
    next_tick = start
    last = {}
    model_ns = 0
    received = []
    sent = []
    i = 0
    torque = 0.0
    try:
      while proc.poll() is None:
        if time.monotonic() - start > seconds + 20:
          raise TimeoutError('child deadline')
        now = time.monotonic_ns()
        records = {r['kind']: r['data'] for r in synthetic_records(now)}
        for service in [s for s in SERVICES if s != 'selfdriveState'] + ['selfdriveState']:
          freq = SERVICE_LIST[service].frequency
          if service != 'selfdriveState' and now - last.get(service, 0) < int(1e9 / max(freq, 1)):
            continue
          last[service] = now
          msg = messaging.new_message(service, 0 if service == 'onroadEvents' else None)
          msg.valid = True
          msg.logMonoTime = now
          if service in records:
            data = dict(records[service])
            if service == 'carState':
              data.update(canValid=True, latEnabled=True, gearShifter='drive', steeringAngleDeg=-2.0, vCruiseCluster=80.0)
            if service == 'modelV2':
              model_ns = now
            if service == 'lateralPlan':
              data['modelMonoTime'] = model_ns
            setattr(msg, service, data)
          if service == 'selfdriveState':
            msg.selfdriveState.enabled = True
            msg.selfdriveState.active = True
            msg.selfdriveState.state = 'enabled'
          elif service == 'liveParameters':
            for key, value in {'valid': True, 'sensorValid': True, 'posenetValid': True, 'steerRatio': 13.0, 'stiffnessFactor': 1.0}.items():
              setattr(msg.liveParameters, key, value)
          elif service == 'livePose':
            msg.livePose.inputsOK = msg.livePose.sensorsOK = msg.livePose.posenetOK = True
          elif service == 'liveCalibration':
            msg.liveCalibration.rpyCalib = [0.0, 0.0, 0.0]
          elif service == 'liveDelay':
            msg.liveDelay.lateralDelay = 0.1
          elif service == 'carOutput':
            msg.carOutput.actuatorsOutput.torque = torque
          elif service == 'carrotMan':
            msg.carrotMan.vTurnSpeed = 100.0
            msg.carrotMan.desiredSpeed = 80.0
          pm.send(service, msg)
          if service == 'selfdriveState':
            sent.append(now)
        while True:
          msg = messaging.recv_one_or_none(sock)
          if msg is None:
            break
          received.append({'message_ns': msg.logMonoTime, 'received_ns': time.monotonic_ns()})
          torque = msg.carControl.actuators.torque
        i += 1
        next_tick += 0.01
        if next_tick < time.monotonic() - 0.05:
          next_tick = time.monotonic()
        time.sleep(max(0.0, next_tick - time.monotonic()))
      if proc.returncode:
        raise RuntimeError(f'child exit {proc.returncode}; see stderr')
    finally:
      if proc.poll() is None:
        proc.terminate()
        proc.wait(timeout=5)
      (output / 'receiver.json').write_text(json.dumps({'received': received, 'sent': sent}))


if __name__ == '__main__':
  p = argparse.ArgumentParser()
  p.add_argument('--output', type=Path, required=True)
  p.add_argument('--seconds', type=float, default=40)
  p.add_argument('--mode', choices=['off', 'on', 'default'], default='off')
  p.add_argument('--backend', choices=['process', 'thread'], default='process')
  p.add_argument('--load-location', choices=['worker', 'control'], default='worker')
  p.add_argument('--stall-seconds', type=float, default=.06)
  p.add_argument('--child', action='store_true')
  p.add_argument('--logger', action='store_true')
  p.add_argument('--record-logs', action='store_true')
  a = p.parse_args()
  from openpilot.system.hardware import PC

  if not PC:
    raise RuntimeError('desktop-only benchmark; never run on a vehicle device')
  if not 2 <= a.seconds <= 120:
    raise ValueError('duration must be 2..120 seconds')
  prefix = os.environ.get('OPENPILOT_PREFIX', '')
  if not prefix.startswith('pr52synthetic-') or not all(c.isalnum() or c == '-' for c in prefix):
    raise RuntimeError('isolated benchmark prefix required')
  params_root = os.environ.get('PARAMS_ROOT', '')
  if not str(Path(params_root).resolve()).startswith('/tmp/pr52-'):
    raise RuntimeError('private synthetic Params root under /tmp/pr52- required')
  if not a.output.resolve().is_relative_to('/tmp'):
    raise RuntimeError('benchmark outputs must remain under /tmp')
  if a.logger:
    from openpilot.system.hardware.hw import Paths
    from openpilot.system.logmessaged import main
    Paths.swaglog_root = staticmethod(lambda: str(a.output / 'swaglog'))
    main()
  elif a.child:
    child(a.output, a.seconds)
  else:
    if not 0 < a.stall_seconds <= 5:
      raise ValueError('stall duration must be 0..5 seconds')
    os.environ['CURVE_BENCH_STALL'] = str(a.stall_seconds)
    os.environ['CURVE_BENCH_BACKEND'] = a.backend
    os.environ['CURVE_BENCH_LOAD'] = a.load_location
    if Path(params_root).exists():
      raise RuntimeError('use a fresh synthetic Params directory for every trial')
    a.output.mkdir(parents=True, exist_ok=False)
    shared = Path('/dev/shm/msgq_' + prefix)
    shared.mkdir(exist_ok=False)
    logger = None
    try:
      if a.record_logs:
        logger = subprocess.Popen([sys.executable, __file__, '--logger', '--output', str(a.output)])
        ipc = Path('/tmp/logmessage' + prefix)
        deadline = time.monotonic() + 5
        while not ipc.exists():
          if logger.poll() is not None or time.monotonic() > deadline:
            raise RuntimeError('test logmessaged startup failed')
          time.sleep(.01)
      parent(a.output, a.seconds, a.mode)
      (a.output/'run-config.json').write_text(json.dumps({'mode':a.mode, 'backend':a.backend,
        'record_logs':a.record_logs, 'seconds':a.seconds, 'stall_seconds':a.stall_seconds}))
    finally:
      if logger is not None:
        logger.terminate()
        logger.wait(timeout=5)
        Path('/tmp/logmessage' + prefix).unlink(missing_ok=True)
      shutil.rmtree(shared)
