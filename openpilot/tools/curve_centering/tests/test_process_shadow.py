from types import SimpleNamespace as NS

import pytest

from openpilot.cereal import car
from openpilot.tools.curve_centering.process_shadow import ExactJoin, ProcessShadow, WIRE, decode
from openpilot.tools.curve_centering.runtime_shadow import ShadowProcessor
from openpilot.tools.curve_centering.tests.test_runtime_shadow import capture_sequence, messages


def observe(monitor, sm=None, **kw):
  if sm is None:
    sm = messages(0)
  defaults = {'feedback':.001, 'roll':0., 'previous':0., 'lateral_started':True,
              'lane_mode':False, 'vw_meb':False, 'safety_limited':False}
  defaults.update(kw)
  cc = car.CarControl.new_message(latActive=True)
  cc.actuators.curvature = kw.get('previous', 0.)
  monitor.observe(sm, cc, NS(active=True, saturated=False, actualLateralAccel=.144, desiredLateralAccel=.144), **defaults)


def test_wire_size_and_no_geometry_or_lac_dictionary_access():
  class NoGeometry:
    action = NS(desiredCurvature=.001)
    meta = NS(laneChangeState='off', desire='none')
    def __getattr__(self, name):
      raise AssertionError('control-side geometry access: '+name)
  monitor = ProcessShadow(start_worker=False, clock=lambda:2_000_000)
  try:
    sm = messages(0)
    sm['modelV2'] = NoGeometry()
    sm['lateralPlan'] = NoGeometry()
    observe(monitor, sm)
    raw = monitor.test_receiver.recv(1024)
    assert len(raw) == WIRE.size == 128
    assert not monitor.failed
    assert decode(raw)['flags']['lat_active']
  finally:
    monitor.close()


def test_full_channel_drops_then_disables_without_blocking():
  clock = [0]
  monitor = ProcessShadow(start_worker=False, clock=lambda:clock[0])
  for i in range(300):
    clock[0] = i*10_000_000
    observe(monitor)
  assert monitor.dropped > 0
  assert monitor.failed and monitor.closed
  assert monitor.failure_reason == 'transport_TimeoutError'


def test_peer_death_and_explicit_close_are_fail_closed():
  monitor = ProcessShadow(start_worker=False)
  monitor.test_receiver.close()
  observe(monitor)
  assert monitor.failed and monitor.closed
  monitor.close()  # idempotent, no join
  sequence = monitor.sequence
  observe(monitor)
  assert monitor.sequence == sequence


@pytest.mark.parametrize('raw', [b'', b'x'*127, b'x'*128, b'x'*129])
def test_rejects_bad_wire(raw):
  with pytest.raises(ValueError):
    decode(raw)


def test_exact_join_matches_previous_capture_processor_and_never_outputs_vehicle_commands():
  clock = [0]
  monitor = ProcessShadow(start_worker=False, clock=lambda:clock[0])
  join, original = ExactJoin(), ShadowProcessor()
  active = 0
  try:
    for capture in capture_sequence():
      clock[0] = capture.tick.now_ns
      for r in capture.records:
        if r['kind'] in join.cache:
          join.add(r['kind'], r['mono_ns'], r['valid'], r['data'])
      sm = messages(capture.tick.model_ns)
      sm.logMonoTime['carState'] = capture.tick.car_state_ns
      sm.logMonoTime['liveParameters'] = capture.tick.parameters_ns
      cc = car.CarControl.new_message(latActive=True)
      cc.actuators.curvature = capture.actual_curvature
      monitor.observe(sm, cc, NS(active=True, saturated=False, actualLateralAccel=.144, desiredLateralAccel=.144),
                      feedback=.001, roll=0., previous=capture.previous, lateral_started=capture.lateral_started,
                      lane_mode=False, vw_meb=False, safety_limited=False)
      result = join.process(decode(monitor.test_receiver.recv(1024)))
      expected = original.process(capture)
      assert result == expected
      active += bool(result['policy_delta_curvature'])
      assert result['vehicle_output'] is False
    assert active > 0
  finally:
    monitor.close()


def test_missing_or_mutated_exact_source_never_uses_latest():
  monitor = ProcessShadow(start_worker=False, clock=lambda:2_000_000)
  join = ExactJoin()
  try:
    observe(monitor)
    packet = decode(monitor.test_receiver.recv(1024))
    assert join.process(packet)['reasons'] == ['missing_exact_source']
    join.add('modelV2', 100, True, {'a':1})
    join.add('modelV2', 100, True, {'a':2})
    assert join.cache['modelV2'][100] == (False, {'a':1})
    join.add('modelV2', 100, True, {'a':1})
    assert join.cache['modelV2'][100][0] is False
    assert join.process(packet)['reasons'] == ['missing_exact_source']
    for i in range(1000):
      join.add('modelV2', i, True, {})
    assert len(join.cache['modelV2']) == 64
  finally:
    monitor.close()


def test_transient_backpressure_recovers_but_sustained_post_startup_pressure_stops():
  clock = [0]
  monitor = ProcessShadow(start_worker=False, clock=lambda:clock[0])
  try:
    clock[0] = 3_000_000_000
    for _ in range(12):
      observe(monitor)
    assert monitor.dropped and not monitor.failed
    while True:
      try:
        monitor.test_receiver.recv(1024)
      except BlockingIOError:
        break
    clock[0] += 10_000_000
    observe(monitor)
    assert monitor.full_since is None and not monitor.failed
    for _ in range(12):
      observe(monitor)
    clock[0] += 210_000_000
    observe(monitor)
    assert monitor.closed and monitor.failure_reason == 'transport_TimeoutError'
  finally:
    monitor.close()


def test_actual_lac_activity_is_not_inferred_from_requested_lateral_activity():
  monitor = ProcessShadow(start_worker=False, clock=lambda:2_000_000)
  try:
    cc = car.CarControl.new_message(latActive=True)
    monitor.observe(messages(0), cc, NS(active=False, saturated=False, actualLateralAccel=.144, desiredLateralAccel=.144),
                    feedback=.001, roll=0., previous=0., lateral_started=True,
                    lane_mode=False, vw_meb=False, safety_limited=False)
    packet = decode(monitor.test_receiver.recv(1024))
    assert packet['flags']['lat_active']
    assert not packet['flags']['lac_active']
  finally:
    monitor.close()
