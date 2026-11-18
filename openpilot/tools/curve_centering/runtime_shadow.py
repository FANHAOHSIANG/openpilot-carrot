"""Legacy thread observer retained for comparisons; production uses process_shadow.

ShadowProcessor and snapshot are reused inside the isolated child only.

Bounded nonblocking queue; no return path into controls, Params, CAN or actuator
objects. Source objects are copied before queueing. All analysis and diagnostics
run outside the control callback. Device timing has NOT been qualified.
"""
from dataclasses import dataclass
from queue import Empty, Full, Queue
import threading
import time

from .control_bridge import ControlBridge, ControlTick
from .observer import Observer


def snapshot(name, message):
  def values(v):
    if len(v) > 64:
      raise ValueError('oversized observation array')
    return list(v)

  def path(p):
    return {'x': values(p.x), 'y': values(p.y)}

  if name == 'modelV2':
    if len(message.laneLines) > 4:
      raise ValueError('oversized lane array')
    return {'position': path(message.position), 'laneLines': [path(p) for p in message.laneLines],
            'laneLineProbs': values(message.laneLineProbs), 'laneLineStds': values(message.laneLineStds),
            'action': {'desiredCurvature': float(message.action.desiredCurvature)},
            'meta': {'laneChangeState': str(message.meta.laneChangeState), 'desire': str(message.meta.desire)}}
  if name == 'lateralPlan':
    return {'modelMonoTime': int(message.modelMonoTime), 'mpcSolutionValid': bool(message.mpcSolutionValid),
            'useLaneLines': bool(message.useLaneLines), 'position': path(message.position),
            'dPathPoints': values(message.dPathPoints)}
  return {k: getattr(message, k) for k in ('vEgo', 'steeringPressed', 'gasPressed', 'brakePressed', 'leftBlinker', 'rightBlinker')}


@dataclass(frozen=True)
class Capture:
  tick: ControlTick
  records: tuple
  previous: float
  lateral_started: bool
  actual_curvature: float
  generation: int


class ShadowProcessor:
  def __init__(self):
    self.generation = None
    self.bridge = ControlBridge()  # always shadow; no selectable actuation mode
    self.observer = Observer()
    self.observation = None
    self.first = True

  def process(self, capture):
    if self.generation != capture.generation:
      self.bridge = ControlBridge()
      self.observer = Observer()
      self.observation = None
      self.first = True
      self.generation = capture.generation
    for record in sorted(capture.records, key=lambda r: r['t']):
      row = self.observer.feed(record)
      if row is not None:
        self.observation = {'row': row, 'model_ns': record['data']['modelMonoTime'],
                            'available_ns': capture.tick.now_ns}
    # Actual consumed previous state anchors A. C remains counterfactual, never
    # confused with an actual command; fresh/reset C starts at the same state.
    self.bridge.previous['A'] = capture.previous
    self.bridge.started['A'] = capture.lateral_started
    if self.first:
      self.bridge.previous['C'] = capture.previous
      self.bridge.started['C'] = capture.lateral_started
      self.first = False
    result = self.bridge.step(capture.tick, self.observation)
    if result['baseline'] is None:
      self.first = True
    result['actual_baseline_error'] = (None if result['baseline'] is None else
                                       result['baseline']['curvature']-capture.actual_curvature)
    return result


class RuntimeShadow:
  def __init__(self, emit, *, start_worker=True, clock=time.monotonic_ns):
    self.emit = emit
    self.clock = clock
    self.queue = Queue(maxsize=4)
    self.failed = False
    self.failure_reason = None
    self.dropped = 0
    self.generation = 0
    self.seen = {}
    self.latest = None
    self.max_capture_ns = 0
    self._stop = threading.Event()
    self.thread = None
    if start_worker:
      self.thread = threading.Thread(target=self._run, name='curve-shadow-only', daemon=True)
      self.thread.start()

  def close(self):
    self._stop.set()  # never join/block the control loop

  def observe(self, sm, cc, lac_log, *, feedback, roll, previous, lateral_started, lane_mode, vw_meb, safety_limited):
    if self.failed or self._stop.is_set():
      return
    started = self.clock()
    try:
      cs, model, plan = sm['carState'], sm['modelV2'], sm['lateralPlan']
      # lane_mode is the already evaluated production source, not an inference
      # from useLaneLines. Encode that boolean for the scalar branch selector.
      tick = ControlTick(started, int(sm.logMonoTime['modelV2']), int(sm.logMonoTime['carState']),
                         int(sm.logMonoTime['liveParameters']), float(model.action.desiredCurvature),
                         float(cs.vEgo), float(feedback), float(roll), bool(cc.latActive),
                         bool(cs.steeringPressed), bool(cs.gasPressed), bool(cs.brakePressed),
                         bool(cs.leftBlinker or cs.rightBlinker or str(model.meta.laneChangeState) != 'off'
                              or str(model.meta.desire) != 'none'),
                         getattr(lac_log, 'saturated', None), safety_limited,
                         all(sm.seen[k] and sm.valid[k] and sm.alive[k] for k in
                             ('modelV2', 'carState', 'liveParameters', 'lateralPlan'))
                         and all(getattr(sm['liveParameters'], k, False) is True for k in ('valid', 'sensorValid', 'posenetValid')),
                         lane_mode, 1.0, 0.0, vw_meb)
      records = []
      for name, message in (('carState', cs), ('modelV2', model), ('lateralPlan', plan)):
        ns = int(sm.logMonoTime[name])
        if self.seen.get(name) != ns:
          records.append({'kind': name, 'mono_ns': ns, 't': ns/1e9,
                          'valid': bool(sm.seen[name] and sm.valid[name] and sm.alive[name]), 'data': snapshot(name, message)})
          self.seen[name] = ns
      # These are this exact control step's measured feedback and actual result.
      # Future controls are not joined backwards onto an earlier model frame.
      records.extend([
        {'kind': 'carControl', 'mono_ns': started, 't': started/1e9, 'valid': True,
         'data': {'latActive': bool(cc.latActive), 'actuators': {'curvature': float(cc.actuators.curvature)}}},
        {'kind': 'controlsState', 'mono_ns': started, 't': started/1e9, 'valid': True,
         'data': {'curvature': float(feedback), 'lateralControlState': {'torqueState': lac_log.to_dict()}}},
      ])
      capture = Capture(tick, tuple(records), float(previous), bool(lateral_started),
                        float(cc.actuators.curvature), self.generation)
      try:
        self.queue.put_nowait(capture)
      except Full:
        self.dropped += 1
        self.generation += 1
        self.seen.clear()  # next accepted item must bring fresh model/plan records
      self.max_capture_ns = max(self.max_capture_ns, self.clock()-started)
    except Exception as exc:
      self.failed = True
      self.failure_reason = 'capture_' + type(exc).__name__
      self.close()

  def _run(self):
    try:
      processor = ShadowProcessor()
      last_emit_ns = None
      while not self._stop.is_set():
        try:
          capture = self.queue.get(timeout=.1)
        except Empty:
          continue
        if capture.generation != self.generation:
          continue  # overflow invalidates queued evidence, not just the missing tick
        result = processor.process(capture)
        if capture.generation != self.generation:
          continue
        self.latest = result
        if last_emit_ns is None or capture.tick.now_ns-last_emit_ns >= 1_000_000_000:
          # Only numerical diagnostic results/reasons, never raw geometry, GPS,
          # source message bodies, VIN/device/route identifiers.
          self.emit({'mode': 'shadow_only', 'vehicle_output': False,
                     'actual_baseline_error': result['actual_baseline_error'],
                     'policy_delta_curvature': result['policy_delta_curvature'],
                     'history_delta_curvature': result['residual_curvature'],
                     'reasons': result['reasons'], 'dropped': self.dropped,
                     'max_capture_ns': self.max_capture_ns})
          last_emit_ns = capture.tick.now_ns
    except Exception as exc:
      self.failed = True
      self.failure_reason = 'worker_' + type(exc).__name__
      self.close()
