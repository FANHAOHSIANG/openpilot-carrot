import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'spas_identity.py'
spec = importlib.util.spec_from_file_location('identity', PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def raw(address, counter, change=None):
  d = bytearray(32 if address == 0x35 else 24)
  d[2] = counter
  if change:
    d[change[0]] = change[1]
  crc = 0
  for b in d[2:] + address.to_bytes(2, 'little'):
    crc ^= b << 8
    for _ in range(8):
      crc = ((crc << 1) ^ (0x1021 if crc & 0x8000 else 0)) & 0xffff
  d[:2] = (crc ^ {24: 0x819d, 32: 0x9f5b}[len(d)]).to_bytes(2, 'little')
  return bytes(d)


class IdentityTests(unittest.TestCase):
  def test_device_accepts_typed_string_and_legacy_bytes(self):
    self.assertTrue(m.device_matches(m.DEVICE))
    self.assertTrue(m.device_matches(m.DEVICE.encode()))
    for value in (None, True, 123, 'wrong', b'wrong', b'\xff', m.DEVICE+' '):
      with self.subTest(value=value):
        self.assertFalse(m.device_matches(value))

  def test_typed_boolean_snapshot_preserves_missing_false_and_true(self):
    import tempfile
    with tempfile.TemporaryDirectory() as root:
      class Params:
        def get(self, key):
          raise AssertionError('Typed get must not be treated as raw bytes')
        def get_param_path(self, key):
          return root+'/'+key
      Path(root, 'IsOnroad').write_bytes(b'1')
      Path(root, 'FirmwareQueryDone').write_bytes(b'0')
      saved = m.snapshot_parameters(Params())
      self.assertEqual(saved['IsOnroad'], '31')
      self.assertEqual(saved['FirmwareQueryDone'], '30')
      self.assertIsNone(saved['ControlsReady'])
      Path(root, 'ControlsReady').write_bytes(b'garbage')
      with self.assertRaises(RuntimeError):
        m.snapshot_parameters(Params())

  def test_boolean_restore_uses_native_typed_writer(self):
    events = []
    class Params:
      def put_bool(self, key, value):
        self.assert_bool(value)
        events.append((key, value))
      def assert_bool(self, value):
        if type(value) is not bool:
          raise AssertionError('Wrong parameter type')
      def remove(self, key): events.append((key, None))
    p = Params()
    for value in ('31', '30', None):
      m.restore_parameter(p, 'IsOnroad', value)
    self.assertEqual(events, [('IsOnroad', True), ('IsOnroad', False), ('IsOnroad', None)])
    with self.assertRaises(ValueError):
      m.restore_parameter(p, 'IsOnroad', 'bad')

  def test_fixed_read_only_tx_contract(self):
    for service in (0x10, 0x11, 0x14, 0x27, 0x28, 0x2e, 0x2f, 0x31, 0x34, 0x3e):
      with self.subTest(service=service), self.assertRaises(ValueError):
        m.packet(bytes([service, 0, 0]))
    self.assertEqual(len(m.READS), 6)
    self.assertEqual(m.packet(bytes.fromhex('22f187')), bytes.fromhex('0322f18700000000'))

  def test_solicited_multiframe_and_wrap(self):
    payload = bytes.fromhex('62f100') + bytes(range(120))
    r = m.Reply(bytes.fromhex('22f100'))
    answer, fc = r.feed(bytes([0x10, len(payload)]) + payload[:6])
    self.assertIsNone(answer)
    self.assertTrue(fc)
    for i, pos in enumerate(range(6, len(payload), 7), 1):
      answer, fc = r.feed((bytes([0x20 | (i & 15)]) + payload[pos:pos+7]).ljust(8, b'\0'))
      self.assertFalse(fc)
    self.assertEqual(answer, payload)

  def test_no_flowcontrol_for_other_did(self):
    with self.assertRaises(ValueError):
      m.Reply(bytes.fromhex('22f100')).feed(bytes.fromhex('101062f110000000'))

  def test_overflow_bad_sequence_and_unsolicited_cf(self):
    for frame in ('120162f100000000', '2100000000000000', '0000000000000000'):
      with self.subTest(frame=frame), self.assertRaises(ValueError):
        m.Reply(bytes.fromhex('22f100')).feed(bytes.fromhex(frame))
    r = m.Reply(bytes.fromhex('22f100'))
    r.feed(bytes.fromhex('101062f100000000'))
    with self.assertRaises(ValueError):
      r.feed(bytes.fromhex('2200000000000000'))

  def test_negative_is_data_not_assumed_identity(self):
    self.assertEqual(m.Reply(bytes.fromhex('22f100')).feed(bytes.fromhex('037f223100000000')),
                     (bytes.fromhex('7f2231'), False))

  def test_park_requires_crc_counter_and_freshness(self):
    g = m.ParkGuard()
    for i in range(12):
      for addr in (0x35, 0xa0):
        g.observe(addr, raw(addr, (250+i) % 256), 1+i*.01)
    self.assertTrue(g.ready(1.12))
    self.assertFalse(g.ready(1.4))
    corrupt = bytearray(raw(0x35, 6)); corrupt[5] = 1
    g.observe(0x35, bytes(corrupt), 1.12)
    self.assertFalse(g.ready(1.12))

  def test_repeated_counters_cannot_arm(self):
    g = m.ParkGuard()
    for i in range(20):
      for addr in (0x35, 0xa0):
        g.observe(addr, raw(addr, 1), 1+i*.01)
    self.assertFalse(g.ready(1.2))

  def test_report_exposes_equal_batch_timestamps_without_relaxing_guard(self):
    g = m.ParkGuard()
    for i in range(12):
      for address in (0x35, 0xa0):
        g.observe(address, raw(address, i), 1.)
    self.assertFalse(g.ready(1.01))
    report = g.report(1.01)
    self.assertEqual(report['0x35']['counts']['same_batch_timestamp'], 11)
    self.assertEqual(report['0x35']['counts']['counter_discontinuities'], 0)
    self.assertEqual(report['0x35']['consecutive'], 1)
    json.dumps(report)

  def test_report_distinguishes_crc_failure_from_missing_frames(self):
    g = m.ParkGuard()
    d = bytearray(raw(0x35, 1)); d[0] ^= 1
    g.observe(0x35, bytes(d), 1.)
    report = g.report(1.01)
    self.assertEqual(report['0x35']['counts']['invalid_crc'], 1)
    self.assertNotEqual(report['0x35']['latest']['crc_expected'], report['0x35']['latest']['crc_received'])
    self.assertEqual(report['0xa0']['counts'], {})
    self.assertFalse(g.ready(1.01))

  def test_gear_pedal_and_any_wheel_cancel(self):
    for addr, change in ((0x35, (24, 1)), (0x35, (5, 1)), (0xa0, (8, 1)), (0xa0, (10, 1)),
                         (0xa0, (12, 1)), (0xa0, (14, 1))):
      with self.subTest(addr=addr, change=change):
        g = m.ParkGuard()
        for i in range(12):
          for a in (0x35, 0xa0):
            g.observe(a, raw(a, i, change if a == addr else None), 1+i*.01)
        self.assertFalse(g.ready(1.12))

  def test_tx_rejects_actuation_even_with_diagnostic_mode(self):
    v = object.__new__(m.Vehicle)
    for data in (bytes.fromhex('0328030100000000'), bytes.fromhex('0210030000000000'), bytes(8)):
      with self.subTest(data=data), self.assertRaises(RuntimeError):
        v.tx(data, ())

  def test_no_query_retry_on_negative_or_timeout(self):
    class Fake:
      def __init__(self, reply):
        self.reply, self.sent, self.pumps = reply, [], 0
      def pump(self):
        self.pumps += 1
        return [(m.RESPONSE, self.reply)] if self.reply is not None and self.pumps > 1 else []
      def tx(self, data, baseline): self.sent.append(data)
      def assert_guard(self, *args): pass
    for reply, status in ((bytes.fromhex('037f223100000000'), 'negative'), (None, 'timeout')):
      f = Fake(reply)
      with patch.object(m.time, 'monotonic', side_effect=iter(i*.1 for i in range(100))), patch.object(m.time, 'sleep'):
        result = m.Vehicle.query(f, bytes.fromhex('22f100'), ())
      self.assertEqual(result['status'], status)
      self.assertEqual(f.sent, [m.packet(bytes.fromhex('22f100'))])

  def test_pid_reuse_never_signals_replacement(self):
    with patch.object(m, 'process', return_value={'start': 'new'}), patch.object(m.os, 'kill') as kill:
      with self.assertRaises(RuntimeError):
        m.send_signal({'pid': 999, 'start': 'old'}, m.signal.SIGCONT)
      kill.assert_not_called()

  def test_recovery_resumes_processes_even_if_parameter_restore_fails(self):
    import tempfile
    import sys
    events = []
    class Params:
      def put_bool(self, *args):
        events.append('param')
        raise RuntimeError('simulated I/O failure')
    with tempfile.TemporaryDirectory() as root:
      snapshot = {'owner': {'pid': 1}, 'params': {}, 'original': ('hyundaiCanfd', 6173),
                  'processes': {'controls': {'pid': 2}, 'manager': {'pid': 3}}, 'result': root+'/restore.json'}
      fake = SimpleNamespace(Params=Params)
      with patch.dict(sys.modules, {'openpilot.common.params': fake}), \
           patch.object(m.select, 'select', return_value=([1], [], [])), patch.object(m.os, 'read', return_value=b''), \
           patch.object(m, 'send_signal', side_effect=lambda p, s: events.append(p['pid'])), \
           patch.object(m, 'Vehicle', side_effect=RuntimeError('no native telemetry')):
        m.recover(snapshot, 1)
      self.assertEqual(events, ['param', 2, 3])
      self.assertFalse(json.loads(Path(snapshot['result']).read_text())['restored'])


if __name__ == '__main__':
  unittest.main()
