import ast
from dataclasses import replace
import hashlib
import math
from numbers import Number
from types import SimpleNamespace as NS

import pytest

from openpilot.cereal import car, log
from openpilot.tools.curve_centering.bridge_demo import synthetic_records
from openpilot.tools.curve_centering.runtime_shadow import RuntimeShadow, ShadowProcessor
from openpilot.tools.curve_centering.source_control import ROOT, SourceControl


class Messages(dict):
  pass


def messages(ns):
  records = synthetic_records(ns)
  sm = Messages()
  for record in records:
    kind = record['kind']
    if kind in ('carState', 'modelV2', 'lateralPlan'):
      schema = {'carState': car.CarState, 'modelV2': log.ModelDataV2, 'lateralPlan': log.LateralPlan}[kind]
      sm[kind] = schema.new_message(**record['data'])
  sm['liveParameters'] = NS(roll=0., valid=True, sensorValid=True, posenetValid=True)
  sm.logMonoTime = dict.fromkeys(sm, ns)
  sm.logMonoTime['lateralPlan'] += 1_000_000
  sm.seen = dict.fromkeys(sm, True)
  sm.valid = dict(sm.seen)
  sm.alive = dict(sm.seen)
  return sm


def lac():
  return NS(saturated=False, to_dict=lambda: {'saturated': False, 'active': True,
                                              'actualLateralAccel': .144, 'desiredLateralAccel': .144})


def capture_sequence():
  clock = [0]
  monitor = RuntimeShadow(lambda _: None, start_worker=False, clock=lambda: clock[0])
  source = SourceControl()
  previous, started = 0., False
  for i in range(601):
    model_ns = i//5*50_000_000
    clock[0] = i*10_000_000+2_000_000
    sm = messages(model_ns)
    sm.logMonoTime['carState'] = i*10_000_000
    sm.logMonoTime['liveParameters'] = i*10_000_000
    step = source.step(speed=12., previous=previous, feedback=.001, action=float(sm['modelV2'].action.desiredCurvature),
                       roll=0., active=True, lateral_started=started)
    cc = car.CarControl.new_message(latActive=True)
    cc.actuators.curvature = step['curvature']
    monitor.observe(sm, cc, lac(), feedback=.001, roll=0., previous=previous, lateral_started=started,
                    lane_mode=False, vw_meb=False, safety_limited=False)
    previous, started = step['curvature'], step['lateral_started']
    assert not monitor.failed
    yield monitor.queue.get_nowait()


def test_real_message_capture_processor_parity_and_nonzero_shadow():
  processor = ShadowProcessor()
  active = 0
  for capture in capture_sequence():
    result = processor.process(capture)
    if result['actual_baseline_error'] is not None:
      # Actual carControl stores float32; scalar comparison accounts for encoding.
      assert abs(result['actual_baseline_error']) < 1e-9
    active += result['injected_delta_curvature'] != 0
    assert not result['vehicle_output']
    assert result['mode'] == 'shadow'
  assert active > 0


def test_queue_overflow_invalidates_evidence_and_is_nonblocking():
  monitor = RuntimeShadow(lambda _: None, start_worker=False, clock=lambda: 2_000_000)
  sm = messages(0)
  cc = car.CarControl.new_message(latActive=True)
  for _ in range(5):
    monitor.observe(sm, cc, lac(), feedback=0., roll=0., previous=0., lateral_started=False,
                    lane_mode=False, vw_meb=False, safety_limited=False)
  assert monitor.queue.qsize() == 4
  assert monitor.dropped == 1 and monitor.generation == 1
  assert all(monitor.queue.get_nowait().generation == 0 for _ in range(4))
  monitor.observe(sm, cc, lac(), feedback=0., roll=0., previous=0., lateral_started=False,
                  lane_mode=False, vw_meb=False, safety_limited=False)
  fresh = monitor.queue.get_nowait()
  assert fresh.generation == 1
  assert {'modelV2', 'lateralPlan'} <= {r['kind'] for r in fresh.records}


def test_snapshot_is_detached_and_contains_no_whole_car_state():
  monitor = RuntimeShadow(lambda _: None, start_worker=False, clock=lambda: 2_000_000)
  sm = messages(0)
  cc = car.CarControl.new_message(latActive=True)
  before = sm['modelV2'].to_dict()
  monitor.observe(sm, cc, lac(), feedback=0., roll=0., previous=0., lateral_started=False,
                  lane_mode=False, vw_meb=False, safety_limited=False)
  capture = monitor.queue.get_nowait()
  assert sm['modelV2'].to_dict() == before
  sm['modelV2'].position.y = [123.]*len(sm['modelV2'].position.y)
  model = next(r['data'] for r in capture.records if r['kind'] == 'modelV2')
  assert model['position']['y'] == before['position']['y']
  assert set(next(r['data'] for r in capture.records if r['kind'] == 'carState')) == {
    'vEgo', 'steeringPressed', 'gasPressed', 'brakePressed', 'leftBlinker', 'rightBlinker'}


def test_invalid_payload_and_generation_change_require_reentry():
  processor = ShadowProcessor()
  captures = list(capture_sequence())
  for capture in captures:
    r = processor.process(capture)
  assert r['injected_delta_curvature'] != 0
  last = captures[-1]
  next_tick = replace(last.tick, now_ns=last.tick.now_ns+10_000_000, messages_valid=False)
  r = processor.process(replace(last, tick=next_tick))
  assert r['injected_delta_curvature'] == 0
  assert r['baseline'] is None
  r = processor.process(replace(last, generation=1))
  assert r['injected_delta_curvature'] == 0


def test_capture_exception_disables_monitor_without_escaping():
  monitor = RuntimeShadow(lambda _: None, start_worker=False)
  monitor.observe({}, None, None, feedback=0., roll=0., previous=0., lateral_started=False,
                  lane_mode=False, vw_meb=False, safety_limited=False)
  assert monitor.failed
  assert monitor.queue.empty()


def test_worker_emitter_failure_isolated():
  monitor = RuntimeShadow(lambda _: (_ for _ in ()).throw(RuntimeError('sink failed')), start_worker=False)
  monitor.queue.put_nowait(next(capture_sequence()))
  monitor._run()
  assert monitor.failed


def control_method(with_tap):
  tree = ast.parse((ROOT/'selfdrive/controls/controlsd.py').read_text())
  cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Controls')
  body = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'state_control')
  gate = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'lateral_control_allowed')
  if not with_tap:
    body.body = [n for n in body.body if not (
      isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) in ('(curve_previous, curve_started)', 'shadow')
      or isinstance(n, ast.If) and ast.unparse(n.test) == 'shadow is not None')]
    # Pin original entire method AST to prevent a self-comparison hiding changes.
    digest = hashlib.sha256(ast.dump(body, include_attributes=False).encode()).hexdigest()
    assert digest == ORIGINAL_METHOD_AST
  source = SourceControl()
  ns = dict(source.namespace, math=math, Number=Number, car=car, CV=NS(KPH_TO_MS=1/3.6),
            MIN_LATERAL_CONTROL_SPEED=.3, ACTUATOR_FIELDS=tuple(car.CarControl.Actuators.schema.fields),
            resolve_vehicle_model_steer_ratio=lambda *args: 15.,
            lateral_vehicle_parameters=lambda sm, cp: sm['liveParameters'],
            set_lane_change_blinkers=lambda cc, meta: None,
            inhibit_faulted_controls=lambda cc, events: None,
            get_lag_adjusted_curvature=lambda *args: .002,
            cloudlog=NS(error=lambda msg: pytest.fail(msg)))
  exec(compile(ast.Module(body=[gate, body], type_ignores=[]), 'full actual state_control', 'exec'), ns)
  return ns['state_control']


ORIGINAL_METHOD_AST = 'e1b333ecd5c4f4b782ba4a826c0c299d38e8af28662038e90269948e98811c97'


def controls():
  sm = messages(0)
  sm['carState'].gearShifter = 'drive'
  sm['carState'].latEnabled = True
  sm['liveParameters'] = NS(roll=0., stiffnessFactor=1., steerRatio=15., angleOffsetDeg=0., valid=True, sensorValid=True, posenetValid=True)
  sm.update(selfdriveState=NS(enabled=True, active=True), onroadEvents=[], longitudinalPlan=NS(),
            radarState=NS(), carrotMan=NS(vTurnSpeed=100.), liveDelay=NS(lateralDelay=.1))
  sm.frame = 0
  sm.recv_frame = {'longitudinalPlan': 0}
  sm.all_checks = lambda names: True
  return NS(sm=sm, desired_curvature=0., lateral_started=False, lateral_startup=NS(update=lambda *a: True),
            CP=NS(brand='hyundai', minSteerSpeed=0., openpilotLongitudinalControl=True,
                  lateralTuning=NS(which=lambda: 'pid')),
            VM=NS(update_geometry=lambda *a: None, update_params=lambda *a: None, calc_curvature=lambda *a: -.001),
            CI=NS(get_pid_accel_limits=lambda *a: (-3., 2.)),
            params=NS(get_float=lambda k: 0., get_int=lambda k: 0, get_bool=lambda k: False),
            carrot_controls=NS(lat_suspend_control=lambda cs, active: active),
            LoC=NS(reset=lambda: None, update=lambda *a: (.25, .3, .4), long_control_state='pid'),
            LaC=NS(reset=lambda: None, update=lambda active, cs, vm, lp, limited, curvature, *a, **kw:
                   (curvature*10 if active else 0., curvature*100, lac())),
            is_vw_meb=False, steer_limited_by_safety=False)


@pytest.mark.parametrize('tap', ['off', 'capture', 'throw', 'runtime', 'process'])
def test_complete_control_method_outputs_unchanged(tap):
  old, new = controls(), controls()
  original, current = control_method(False), control_method(True)
  observed = []
  clock = [2_000_000]
  processor = ShadowProcessor()
  if tap == 'runtime':
    new.curve_shadow = RuntimeShadow(lambda _: None, start_worker=False, clock=lambda: clock[0])
  if tap == 'process':
    from openpilot.tools.curve_centering.process_shadow import ProcessShadow
    new.curve_shadow = ProcessShadow(start_worker=False, clock=lambda: clock[0])
  if tap == 'capture':
    new.curve_shadow = NS(observe=lambda *a, **kw: observed.append(kw))
  elif tap == 'throw':
    new.curve_shadow = NS(observe=lambda *a, **kw: (_ for _ in ()).throw(RuntimeError('diagnostic failed')))
  for i in range(300):
    for c in (old, new):
      c.sm['carState'].latEnabled = i % 70 != 0
      c.sm['carState'].steeringPressed = i % 50 < 10
      c.sm['modelV2'].action.desiredCurvature = math.sin(i/20)*.01
      c.sm['lateralPlan'].useLaneLines = i % 70 > 50
    clock[0] = i*10_000_000+2_000_000
    for c in (old, new):
      c.sm.logMonoTime.update(modelV2=i*10_000_000, carState=i*10_000_000, liveParameters=i*10_000_000, lateralPlan=i*10_000_000+1_000_000)
    cc_old, _ = original(old)
    cc_new, _ = current(new)
    assert cc_old.to_dict() == cc_new.to_dict()
    if tap == 'runtime':
      assert not new.curve_shadow.failed
      result = processor.process(new.curve_shadow.queue.get_nowait())
      if result['actual_baseline_error'] is not None:
        assert abs(result['actual_baseline_error']) < 1e-9
    if tap == 'process':
      from openpilot.tools.curve_centering.process_shadow import decode
      packet = decode(new.curve_shadow.test_receiver.recv(1024))
      assert packet['values'][5] == cc_new.actuators.curvature
      assert not new.curve_shadow.failed
    assert old.desired_curvature == new.desired_curvature
    assert old.lateral_started == new.lateral_started
  if tap == 'process':
    new.curve_shadow.close()
  assert len(observed) == (300 if tap == 'capture' else 0)
  if tap == 'throw':
    assert new.curve_shadow is None


@pytest.mark.parametrize('value,expected', [(None, True), ('1', True), ('0', False), ('', False), ('invalid', False)])
def test_runtime_default_shadow_and_explicit_disable(value, expected):
  tree = ast.parse((ROOT/'selfdrive/controls/controlsd.py').read_text())
  cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Controls')
  init = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '__init__')
  condition = next(n for n in init.body if isinstance(n, ast.If) and 'CURVE_CENTERING_SHADOW' in ast.unparse(n.test))
  env = {} if value is None else {'CURVE_CENTERING_SHADOW': value}
  assert eval(compile(ast.Expression(condition.test), '<startup-condition>', 'eval'), {'os': NS(getenv=env.get)}) is expected
  assert not condition.orelse
