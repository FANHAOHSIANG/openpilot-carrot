"""CPU checks for freshness, native handoff and actual C4 approval call sites."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace as N
import unittest
from unittest.mock import patch

ROOT = Path(os.environ.get('C4_SOURCE_ROOT', str(Path(__file__).resolve().parents[4]))).resolve()
SOURCE = ROOT / 'openpilot/selfdrive/modeld/jetlink'


def load(path, name):
  spec = importlib.util.spec_from_file_location(name, path)
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  return module


parked = load(SOURCE / 'parked.py', 'parked')
peer_rules = load(ROOT / 'openpilot/common/jetlink_peer.py', 'peer_rules')
PEER = dict(protocol=3, backend='ort', device='ane-Apple_M4', carrot_host='mac')


def sample(now=10.):
  messages = dict(carState=N(canValid=True, canTimeout=False, standstill=True, steeringPressed=False, gearShifter='park', vEgo=0., vEgoRaw=0.),
                  selfdriveState=N(enabled=False, active=False),
                  carControl=N(enabled=False, latActive=False, longActive=False))
  return messages, dict.fromkeys(parked.SERVICES, True), dict.fromkeys(parked.SERVICES, now)


def definitions(path, names, namespace):
  tree = ast.parse(path.read_text())
  selected = [node for node in tree.body if getattr(node, 'name', None) in names]
  assert len(selected) == len(names)
  exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)
  return namespace


class GateTests(unittest.TestCase):
  def test_only_fresh_parked_disabled_can_is_accepted(self):
    self.assertTrue(parked.stationary_disabled(10., *sample()))
    for service, fields in [('carState', dict(canValid=False, canTimeout=True, standstill=False, gearShifter='drive',
                                            vEgo=.01, vEgoRaw=.01)),
                            ('selfdriveState', dict(enabled=True, active=True)),
                            ('carControl', dict(enabled=True, latActive=True, longActive=True))]:
      for field, value in fields.items():
        with self.subTest(field=field):
          messages, valid, received = sample()
          setattr(messages[service], field, value)
          self.assertFalse(parked.stationary_disabled(10., messages, valid, received))

  def test_missing_unknown_reverse_or_neutral_gear_is_rejected(self):
    for gear in ('reverse', 'neutral', 'unknown', 'P', None):
      data = sample(); data[0]['carState'].gearShifter = gear
      self.assertFalse(parked.stationary_disabled(10., *data))

  def test_nonfinite_and_negative_motion_is_rejected(self):
    for name in ('vEgo', 'vEgoRaw'):
      for speed in (float('nan'), float('inf'), -float('inf'), -.01, -.5):
        data = sample(); setattr(data[0]['carState'], name, speed)
        self.assertFalse(parked.stationary_disabled(10., *data))

  def test_every_service_must_be_valid_and_recent(self):
    for service in parked.SERVICES:
      data = sample(); data[1][service] = False
      self.assertFalse(parked.stationary_disabled(10., *data))
      for stamp in (9.75, 9., 10.01):
        data = sample(); data[2][service] = stamp
        self.assertFalse(parked.stationary_disabled(10., *data))

  def test_missing_message_field_and_timestamp_fail_closed(self):
    for index in (0, 1, 2):
      data = sample(); del data[index]['carControl']
      self.assertFalse(parked.stationary_disabled(10., *data))
    data = sample(); del data[0]['carState'].canTimeout
    self.assertFalse(parked.stationary_disabled(10., *data))

  def test_hold_resets_after_motion_or_bad_data(self):
    gate = parked.ParkedGate()
    self.assertFalse(gate.update(10., *sample(10.)))
    self.assertFalse(gate.update(11.99, *sample(11.99)))
    self.assertTrue(gate.update(12., *sample(12.)))
    invalid = sample(12.01); invalid[0]['carState'].gearShifter = 'drive'
    self.assertFalse(gate.update(12.01, *invalid))
    self.assertFalse(gate.update(12.02, *sample(12.02)))
    self.assertTrue(gate.update(14.02, *sample(14.02)))

  def test_clock_rollback_restarts_hold(self):
    gate = parked.ParkedGate(); gate.update(10., *sample(10.))
    self.assertFalse(gate.update(9., *sample(9.)))
    self.assertFalse(gate.update(10., *sample(10.)))

  def test_ack_requires_recent_completed_native_handoff(self):
    with tempfile.TemporaryDirectory() as directory:
      p = Path(directory) / 'status'
      self.assertFalse(parked.fallback_ack(10., p))
      for record in ({}, [], {'updated': 'invalid'}, {'updated': 10., 'active': True, 'parked_switch_ready': True},
                     {'updated': 10., 'active': False, 'parked_switch_ready': False},
                     {'updated': 9.75, 'active': False, 'parked_switch_ready': True},
                     {'updated': 11., 'active': False, 'parked_switch_ready': True}):
        p.write_text(json.dumps(record)); self.assertFalse(parked.fallback_ack(10., p))
      p.write_text(json.dumps(dict(updated=10., active=False, parked_switch_ready=True)))
      self.assertTrue(parked.fallback_ack(10., p))
      p.write_text('{invalid'); self.assertFalse(parked.fallback_ack(10., p))

  def test_disabled_window_never_subscribes_or_grants(self):
    with tempfile.TemporaryDirectory() as directory, patch.object(parked, 'ENABLE', Path(directory) / 'disabled'):
      window = parked.ParkedWindow()
      self.assertFalse(window()); self.assertIsNone(window.sm)

  def test_enabled_window_uses_current_messaging_namespace(self):
    created = []
    class SM:
      def __init__(self, services): created.append(services)
      def update(self, _):
        self.messages, self.valid, self.recv_time = sample(time.monotonic())
        self.alive = self.valid
      def __getitem__(self, key): return self.messages[key]
    with tempfile.TemporaryDirectory() as directory:
      flag = Path(directory) / 'enabled'; flag.touch()
      with patch.object(parked, 'ENABLE', flag), patch.dict('sys.modules', {'openpilot.cereal.messaging': N(SubMaster=SM)}):
        window = parked.ParkedWindow()
        self.assertFalse(window())  # No hold or native handoff acknowledgement yet.
        self.assertIsNotNone(window.sm)
        self.assertEqual(created, [list(parked.SERVICES)])


class IntegrationTests(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
    self.root = Path(self.temp.name)
    self.now = 10.
    self.enable = self.root / 'enable'; self.enable.touch()
    self.status = self.root / 'model-status'
    self.remote = dict(state='ready', peer=PEER, transport='usb')
    self.namespace = dict(time=N(monotonic=lambda: self.now), json=json, os=os,
                          MODEL_STATUS=self.status, PARKED_ENABLE=self.enable, SERVICES=parked.SERVICES, PARKED_MAX_AGE=parked.MAX_AGE,
                          stationary_disabled=parked.stationary_disabled, may_provision=peer_rules.may_provision,
                          state=lambda: self.remote, model_name=lambda spec: 'test')
    definitions(SOURCE / 'model.py', {'may_join', 'JoiningModel'}, self.namespace)
    self.model = self.namespace['JoiningModel'].__new__(self.namespace['JoiningModel'])
    self.closed = []; self.resets = []; self.native = []
    self.model.__dict__.update(phase_enabled=False, parked_switch=False, parked_small_runs=0, parked_native_at=0., parked_status=False,
                              join_allowed=False, next_status=0., active=True, ready=True, error='', spec=N(sha256='a'*64),
                              client=N(close=lambda: self.closed.append(True)), connection=None, small_runs=3,
                              small=N(reset=lambda: self.resets.append(True), run=lambda *args: self.native_result()),
                              preparation=None, warp=None, next_join=100., reset=False)
    self.native_output = {'native': True}
    self.log_context = patch.dict('sys.modules', {'openpilot.common.swaglog': N(cloudlog=N())})
    self.log_context.start(); self.addCleanup(self.log_context.stop)

  def native_result(self):
    self.native.append(True)
    return self.native_output

  def sm(self, **changes):
    data = sample(self.now)
    for key, value in changes.items(): setattr(data[0]['carState'], key, value)
    class SM:
      valid, alive, recv_time = data[1], data[1], data[2]
      def __getitem__(self, key): return data[0][key]
    return SM()

  def step(self, **changes):
    self.model.update(self.sm(**changes), N())
    return self.model.run({}, {}, {}, False)

  def test_remote_closed_native_reset_before_ack_then_three_outputs(self):
    for index in range(3):
      self.assertEqual(self.step(), {'native': True})
      self.assertFalse(json.loads(self.status.read_text())['parked_switch_ready'])
      self.now += .1
    self.model.update(self.sm(), N())
    self.assertTrue(parked.fallback_ack(self.now, self.status))
    self.assertEqual(self.closed, [True]); self.assertEqual(self.resets, [True])
    self.assertFalse(self.model.active); self.assertFalse(self.model.join_allowed)

  def test_no_native_output_never_acknowledges(self):
    self.native_output = None
    for _ in range(6): self.step(); self.now += .1
    self.assertEqual(self.model.parked_small_runs, 0)
    self.assertFalse(parked.fallback_ack(self.now, self.status))

  def test_leave_park_revokes_ack_immediately_and_preserves_local_model(self):
    for _ in range(4): self.step(); self.now += .1
    self.assertTrue(parked.fallback_ack(self.now, self.status))
    self.model.update(self.sm(gearShifter='drive', standstill=False, vEgo=.5, vEgoRaw=.5), N())
    self.assertFalse(self.model.parked_switch); self.assertFalse(self.model.join_allowed)
    self.assertFalse(parked.fallback_ack(self.now, self.status))
    self.assertEqual(self.model.run({}, {}, {}, False), {'native': True})

  def test_invalid_can_revokes_ack(self):
    for _ in range(4): self.step(); self.now += .1
    self.model.update(self.sm(canValid=False), N())
    self.assertFalse(parked.fallback_ack(self.now, self.status))

  def test_native_outputs_that_stop_do_not_keep_ack_alive(self):
    for _ in range(4): self.step(); self.now += .1
    self.native_output = None
    self.step(); self.now += .3
    self.model.update(self.sm(), N())
    self.assertFalse(parked.fallback_ack(self.now, self.status))

  def test_active_controls_revoke_window_and_block_new_join(self):
    for _ in range(4): self.step(); self.now += .1
    sm = self.sm(); sm['selfdriveState'].enabled = True; sm['carControl'].enabled = True
    self.model.update(sm, N())
    self.assertFalse(self.model.parked_switch); self.assertFalse(self.model.join_allowed)
    self.assertFalse(parked.fallback_ack(self.now, self.status))

  def test_opt_in_does_not_join_while_moving_even_with_steering_override(self):
    sm = self.sm(gearShifter='drive', standstill=False, vEgo=1., vEgoRaw=1., steeringPressed=True)
    self.model.update(sm, N())
    self.assertFalse(self.model.join_allowed)
    self.enable.unlink()
    self.model.update(sm, N())
    self.assertTrue(self.model.join_allowed)  # Original upstream rule, with opt-in disabled.

  def test_unknown_peer_never_pauses(self):
    self.remote['peer'] = dict(protocol=3, backend='trt', device='orin', carrot_host='jetson')
    self.model.update(self.sm(), N())
    self.assertFalse(self.model.parked_switch); self.assertEqual(self.closed, [])

  def test_pending_connection_cancelled_without_adopting_remote(self):
    pending = []; self.model.connection = N(close=lambda: pending.append(True))
    self.step()
    self.assertEqual(pending, [True]); self.assertIsNone(self.model.connection)

  def test_daemon_window_requires_hold_and_modeld_ack(self):
    with patch.object(parked, 'ENABLE', self.enable), patch.object(parked, 'fallback_ack', lambda now: parked_ack(now)), \
         patch.object(parked, 'time', N(monotonic=lambda: self.now)):
      parked_ack = lambda now: json.loads(self.status.read_text()).get('parked_switch_ready', False) if self.status.exists() else False
      window = parked.ParkedWindow()
      owner = self
      class SM:
        valid = alive = dict.fromkeys(parked.SERVICES, True)
        def update(self, timeout): self.messages, _, self.recv_time = sample(owner.now)
        def __getitem__(self, key): return self.messages[key]
      window.sm = SM()
      for _ in range(20):
        self.step(); self.assertFalse(window()); self.now += .1
      self.now = 12.01
      self.step(); self.assertTrue(window())
      self.enable.unlink(); self.assertFalse(window())

  def test_daemon_approval_preserves_offroad_and_rejects_unknown_peer(self):
    namespace = dict(may_provision=peer_rules.may_provision, session_mode=lambda: 'usb', PARKED_WINDOW=lambda: True)
    definitions(SOURCE / 'daemon.py', {'setup_allowed'}, namespace)
    onroad = N(get_bool=lambda key: key == 'IsOnroad')
    offroad = N(get_bool=lambda key: key == 'IsOffroad')
    self.assertTrue(namespace['setup_allowed'](onroad, PEER))
    self.assertFalse(namespace['setup_allowed'](onroad, {'protocol': 3}))
    self.assertFalse(namespace['setup_allowed'](onroad, dict(PEER, protocol=2)))
    self.assertTrue(namespace['setup_allowed'](offroad, PEER))
    namespace['PARKED_WINDOW'] = lambda: False
    self.assertFalse(namespace['setup_allowed'](onroad, PEER))


class ApprovalTests(unittest.TestCase):
  def setUp(self):
    self.allowed = True
    self.saved = []
    self.validated = []
    self.requested = []
    class Deferred(RuntimeError): pass
    class Missing(RuntimeError): pass
    class Changed(RuntimeError): pass
    self.Deferred, self.Missing = Deferred, Missing
    self.spec = N(sha256='b'*64, to_dict=lambda: {'sha256': 'b'*64})
    self.original = N(send=lambda *args: self.requested.append(args))
    self.client = N(t=self.original, state=lambda: {'loaded': 'b'*64})
    self.client.ensure_engine = self.engine
    namespace = dict(re=__import__('re'), time=time, SPEC=N(sha256='a'*64, nbytes=1, frame_skip=1), CACHE=Path('/unused'),
                     may_provision=peer_rules.may_provision, approved_spec=lambda cache: None,
                     remember_spec=lambda cache, spec: self.saved.append(spec),
                     validate_model_spec=lambda spec: self.validated.append(spec), validate_spec=lambda spec: None,
                     PreparationDeferred=Deferred, EngineMissing=Missing, ModelChanged=Changed, LinkTimeout=TimeoutError)
    definitions(SOURCE / 'mac.py', {'require_setup', 'PreparationTransport', 'prepare'}, namespace)
    self.prepare = namespace['prepare']
    self.after_engine = lambda: None

  def engine(self, selected, nbytes, **kwargs):
    self.assertEqual(selected, 'b'*64)
    self.client.t.send('request')
    kwargs['should_stop']()
    self.after_engine()
    return self.spec

  def call(self):
    return self.prepare(self.client, dict(PEER, loaded='b'*64), lambda: self.allowed,
                        lambda: True, lambda *args: None, cache=Path('/unused'))

  def test_ready_parked_app_pick_validated_and_saved(self):
    self.assertIs(self.call(), self.spec)
    self.assertEqual(self.saved, [self.spec]); self.assertEqual(self.validated, [self.spec])
    self.assertIs(self.client.t, self.original)

  def test_lost_parked_gate_before_approval_never_saves_or_requests(self):
    self.allowed = False
    with self.assertRaises(self.Deferred): self.call()
    self.assertEqual(self.saved, []); self.assertEqual(self.requested, [])

  def test_leaving_park_after_engine_response_cancels_save_and_restores_transport(self):
    self.after_engine = lambda: setattr(self, 'allowed', False)
    with self.assertRaises(self.Deferred): self.call()
    self.assertEqual(self.saved, []); self.assertIs(self.client.t, self.original)

  def test_unready_app_engine_never_uploaded_or_approved(self):
    def missing(*args, **kwargs): raise self.Missing()
    self.client.ensure_engine = missing
    with self.assertRaises(self.Deferred): self.call()
    self.assertEqual(self.saved, []); self.assertIs(self.client.t, self.original)

  def test_changed_hello_pick_never_approved(self):
    self.client.state = lambda: {'loaded': 'c'*64}
    with self.assertRaises(RuntimeError): self.call()
    self.assertEqual(self.saved, []); self.assertEqual(self.requested, [])


if __name__ == '__main__':
  unittest.main()

