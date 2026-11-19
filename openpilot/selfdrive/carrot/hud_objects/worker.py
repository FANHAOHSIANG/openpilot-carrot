"""Low-priority, display-only object inference on the C4 ROAD camera."""
from collections import Counter
import ctypes
import json
import multiprocessing
import os
import signal
import stat
import time

from openpilot.selfdrive.carrot.hud_objects.transport import HUD_PATH, SHARED_TRAFFIC_PATH, capture_monotonic, write_snapshot

TRAFFIC = frozenset(('car', 'truck', 'bus', 'motorcycle', 'bicycle', 'person'))
MAX_AGE = 1.0
POLL = .10
RECOVERY = 3.0
CPU_BUSY = 'low-priority CPUs busy'
LOW_PRIORITY_CPUS = frozenset(range(4))


def suspension_reason(sm, params, cores=LOW_PRIORITY_CPUS):
  if not (params.get_bool('C4HudObjects') and params.get_bool('C4HudUsbConnected') and params.get_int('ClusterHud') == 1):
    return 'display disabled or USB panel disconnected'
  if not params.get_bool('IsOnroad') or any(params.get_bool(key) for key in ('IsOffroad', 'DoShutdown', 'DoReboot', 'DoUninstall')):
    return 'device offroad or stopping'
  if params.get_bool('UsbGpuLoading'):
    return 'driving model loading'
  if not sm.all_alive(('modelV2', 'deviceState')) or not sm.all_valid(('modelV2', 'deviceState')):
    return 'waiting for valid deviceState and modelV2'
  model, device = sm['modelV2'], sm['deviceState']
  if not device.started or str(device.thermalStatus) != 'green':
    return 'device stopped or warm'
  cpus = list(device.cpuUsagePercent)
  if not (0 < device.memoryUsagePercent < 90 and cores and len(cpus) > max(cores) and all(0 <= x <= 100 for x in cpus)):
    return 'CPU or memory headroom low or unavailable'
  age = time.clock_gettime(time.CLOCK_BOOTTIME) - model.timestampEof / 1e9
  if not (0 <= age <= .150 and 0 < model.modelExecutionTime <= .050 and 0 <= model.frameDropPerc <= 1.):
    return 'main model late, slow or dropping frames'
  if sum(cpus[i] for i in cores) >= len(cores) * 95:
    return CPU_BUSY
  return None


def fresh_batch(batch, camera, kinds, now):
  if not isinstance(batch, dict) or batch.get('camera') != camera:
    return False
  stamp, objects = batch.get('t'), batch.get('objects')
  if type(stamp) not in (float, int) or not 0 < stamp <= now or now - stamp >= MAX_AGE:
    return False
  if not isinstance(objects, list) or len(objects) > 32:
    return False
  for row in objects:
    if not isinstance(row, (list, tuple)) or len(row) != 6 or not isinstance(row[0], str) or row[0] not in kinds:
      return False
    if not all(type(x) in (float, int) and 0 <= x <= 1 for x in row[1:]):
      return False
    _, x, y, w, h, _ = row
    if w <= 0 or h <= 0 or x-w/2 < -1e-5 or x+w/2 > 1.00001 or y-h < -1e-5:
      return False
  return True


def wide_observation(path, now):
  try:
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW), 'rb') as stream:
      if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
        return None
      raw = stream.read(16385)
    if len(raw) <= 16384:
      batch = json.loads(raw)
      if fresh_batch(batch, 'wideRoad', TRAFFIC, now) and type(batch.get('version')) is int and batch['version'] == 1:
        metadata = {key: batch[key] for key in ('frame_id', 'timestamp_eof_ns')
                    if type(batch.get(key)) is int and 0 <= batch[key] <= 2**64 - 1}
        return {'t': batch['t'], 'camera': 'wideRoad', **metadata, 'objects': [r for r in batch['objects'] if r[0] != 'person']}
  except (OSError, ValueError, RecursionError):
    pass
  return None


class Output:
  def __init__(self, path, report=None):
    self.path = path
    self.report = report
    self.last = None
    self.logged_stamps = {}

  def write(self, batches, now):
    fresh = sorted((b for b in batches.values() if 0 <= now-b['t'] < MAX_AGE), key=lambda b: b['t'])
    if fresh == self.last:
      return
    latest = fresh[-1] if fresh else {'camera': 'road', 't': now, 'objects': []}
    write_snapshot(self.path, {'version': 1, **latest, 'batches': fresh})
    self.last = fresh
    if self.report is not None:
      for detector, batch in batches.items():
        camera, stamp = batch['camera'], batch['t']
        source = detector, camera
        if not 0 <= now - stamp < MAX_AGE or stamp <= self.logged_stamps.get(source, 0.):
          continue
        # At most one rlog record per new published capture and detector, even
        # if the same snapshot is reused on every 10 Hz HUD poll. The geometry
        # matches the HUD wire format (normalized center-x, bottom-y, w, h).
        self.logged_stamps[source] = stamp
        objects = [[row[0], *(round(value, 4) for value in row[1:])] for row in batch['objects']]
        self.report('c4HudObjectsFrame', camera=camera, detector=detector, objects=objects,
                    count=len(objects), timestamp_eof_ns=batch.get('timestamp_eof_ns'),
                    age_ms=round(1000 * (now - stamp)), frame_id=batch.get('frame_id'))


class StatusLog:
  def __init__(self, report):
    self.report = report
    self.next_log = 0.
    self.gates = Counter()

  def update(self, now, reason, status):
    # Retain short interruptions between reports, and include steady-state
    # heartbeats so an individual uploaded rlog segment can explain a blank HUD.
    self.gates[reason or 'ready'] += 1
    if now >= self.next_log:
      self.report('c4HudObjectsState', gate=reason or 'ready', status=status, gate_samples=dict(self.gates))
      self.gates.clear()
      self.next_log = now + 5.


def read_camera(client, last_frame, pack, convert):
  if not client.is_connected() and not client.connect(False):
    return None
  buf = client.recv(timeout_ms=100)
  if buf is None:
    return None
  frame = (int(client.frame_id), int(client.timestamp_eof))
  stamp = capture_monotonic(frame[1])
  if frame == last_frame or not 0 <= time.monotonic() - stamp <= .20:
    return None
  # pack_nv12 copies both visible planes, including cameras with padded stride or UV offset.
  pixels = pack(buf.data, buf.width, buf.height, buf.stride, buf.uv_offset)
  if int(buf.frame_id) != frame[0]:
    return None
  return frame, stamp, convert(pixels)


def inference_child(pipe, parent_pid):
  # A native DNN call can block in C. It cannot survive a killed/restarted manager process.
  if ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGKILL, 0, 0, 0) != 0 or os.getppid() != parent_pid:
    return
  # Bound the child before loading NumPy/OpenCV. Library threads inherit the
  # calling thread's affinity and idle scheduling class.
  cores = os.sched_getaffinity(0) & LOW_PRIORITY_CPUS
  if not cores:
    return
  # The multiprocessing bootstrap may already have imported native libraries.
  for tid in os.listdir('/proc/self/task'):
    try:
      os.sched_setaffinity(int(tid), cores)
      os.sched_setscheduler(int(tid), os.SCHED_IDLE, os.sched_param(0))
    except ProcessLookupError:
      continue
  for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[name] = '1'
  import cv2
  from msgq.visionipc import VisionIpcClient, VisionStreamType
  from openpilot.selfdrive.carrot.hud_objects.detectors import build_detector
  from openpilot.selfdrive.carrot.xiaoge.nv12 import pack_nv12
  cv2.setNumThreads(1)
  client = VisionIpcClient('camerad', VisionStreamType.VISION_STREAM_ROAD, True)
  models = {}
  last_frame = None
  while True:
    name = pipe.recv()
    started = time.process_time()
    try:
      if name not in models:
        models[name] = build_detector(name)
      frame = read_camera(client, last_frame, pack_nv12, lambda p: cv2.cvtColor(p, cv2.COLOR_YUV2RGB_NV12))
      batch = None
      if frame:
        last_frame, stamp, image = frame
        batch = {'camera': 'road', 't': stamp, 'frame_id': last_frame[0],
                 'timestamp_eof_ns': last_frame[1], 'objects': models[name](image)}
      pipe.send((batch, time.process_time()-started, None))
    except Exception as exc:
      models.pop(name, None)
      pipe.send((None, time.process_time()-started, f'{type(exc).__name__}: {exc}'[:200]))


class InferenceProcess:
  def __init__(self):
    ctx = multiprocessing.get_context('spawn')
    self.pipe, child_pipe = ctx.Pipe()
    self.process = ctx.Process(target=inference_child, args=(child_pipe, os.getpid()), daemon=True)
    self.process.start()
    child_pipe.close()

  def close(self):
    self.process.kill()
    self.process.join(.25)
    self.pipe.close()


class Worker:
  def __init__(self, output, shared=SHARED_TRAFFIC_PATH, factory=InferenceProcess, warn=print):
    self.output, self.shared, self.factory, self.warn = output, shared, factory, warn
    self.process = None
    self.pending = None
    self.deadline = 0.
    self.cooldown = 0.
    self.due = {'traffic': 0., 'cone': 0.}
    self.batches = {}
    self.recover_until = 0.
    self.inference_recover_until = 0.
    self.status = 'waiting for first frame'

  def stop(self):
    if self.process is not None:
      self.process.close()
      self.process = None
    self.pending = None

  def publish(self, now, reuse):
    visible = self.batches.copy()
    narrow = visible.get('traffic')
    if reuse and (narrow is None or not 0 <= now - narrow['t'] < MAX_AGE):
      wide = wide_observation(self.shared, now)
      if wide:
        visible['traffic'] = wide
    self.output.write(visible, now)
    return visible.get('traffic', {}).get('camera') == 'wideRoad'

  def tick(self, now, allowed, reuse, *, cpu_busy=False):
    if not allowed:
      self.stop()
      self.recover_until = now + RECOVERY
      self.batches.clear()
      self.output.write(self.batches, now)
      return
    if cpu_busy:
      self.stop()
      self.batches.clear()
      self.inference_recover_until = now + RECOVERY
    if now < self.recover_until:
      self.status = 'waiting for stable main model'
      return
    if cpu_busy or now < self.inference_recover_until:
      shared = self.publish(now, reuse)
      self.status = 'CPU busy; reusing wide-camera result' if shared else 'waiting for CPU headroom'
      return
    if self.pending:
      name = self.pending
      if not self.process.process.is_alive() or now >= self.deadline:
        self.status = f'{name} worker stopped or timed out'
        self.warn(f'C4 HUD {self.status}')
        self.stop()
        self.due[name] = now + 30.
        self.cooldown = now + RECOVERY
        self.batches.pop(name, None)
      elif self.process.pipe.poll():
        try:
          batch, cpu, error = self.process.pipe.recv()
        except (EOFError, OSError):
          batch, cpu, error = None, 0., 'inference worker disconnected'
          self.stop()
        self.pending = None
        self.cooldown = now + max(.12, 6. * cpu)
        if error:
          self.status = f'{name} inference error'
          self.warn(f'C4 HUD {name}: {error}')
          self.due[name] = now + 30.
        if fresh_batch(batch, 'road', {'cone'} if name == 'cone' else TRAFFIC, now):
          self.batches[name] = batch
          self.status = f'{name}: {len(batch["objects"])} observations, age {now-batch["t"]:.2f}s'
        elif batch is not None or error:
          self.batches.pop(name, None)
          if not error:
            self.status = f'{name}: late or invalid result'
        else:
          self.batches.pop(name, None)
          self.status = f'{name}: waiting for a fresh ROAD camera frame'
    self.publish(now, reuse)
    if self.pending or now < self.cooldown:
      return
    name = min(self.due, key=self.due.get)
    if now < self.due[name]:
      return
    try:
      if self.process is None:
        self.process = self.factory()
      self.process.pipe.send(name)
    except (EOFError, OSError) as exc:
      self.status = 'could not launch inference'
      self.warn(f'C4 HUD {self.status}: {exc}')
      self.stop()
      self.cooldown = now + 5.
      return
    self.pending, self.deadline = name, now + 10.
    self.due[name] = now + (.40 if name == 'traffic' else .80)


def main():
  import openpilot.cereal.messaging as messaging
  from openpilot.common.params import Params
  from openpilot.common.swaglog import cloudlog
  cores = os.sched_getaffinity(0) & LOW_PRIORITY_CPUS
  params = Params()
  sm = messaging.SubMaster(['modelV2', 'deviceState'])
  output = Output(HUD_PATH, report=cloudlog.event)
  status_log = StatusLog(cloudlog.event)
  worker = Worker(output, warn=cloudlog.warning)
  output.write({}, time.monotonic())
  worker.recover_until = time.monotonic() + RECOVERY
  try:
    while True:
      sm.update(0)
      reason = suspension_reason(sm, params, cores)
      now = time.monotonic()
      reuse = params.get_bool('ShareData') and params.get_bool('OnnxTruckEnabled')
      can_display = reason in (None, CPU_BUSY)
      worker.tick(now, can_display, reuse, cpu_busy=(reason == CPU_BUSY))
      status_log.update(now, reason, worker.status if can_display else 'suspended')
      time.sleep(POLL)
  finally:
    worker.stop()
    output.write({}, time.monotonic())
