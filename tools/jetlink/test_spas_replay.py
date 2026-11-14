"""Replay the existing SPAS session entirely in memory."""
from types import SimpleNamespace

import pytest

from opendbc.car.hyundai.spas import RESPONSE, SPAS, Session, frame
from tools.jetlink.spas_replay import decode_reply, summarize_rlog


class Replay:
  def __init__(self):
    self.session = Session(0)
    self.tick = 0
    self.sequence = 0
    self.effects = []
    self.step(20, request=None)
    self.step()
    assert self.session.state == 'extended'

  def step(self, ticks=1, *, stock=True, reply=None, driver=False, request='trial'):
    for i in range(ticks):
      self.tick += 1
      now = 10 + self.tick / 100
      if stock and self.tick % 2 == 0:
        for address in SPAS:
          sample = frame(address, self.sequence % 256, None, 0)
          self.session.observe(sample.address, sample.src, sample.dat, now)
        self.sequence += 1
      if reply is not None and i == 0:
        data = bytes.fromhex(reply)
        self.session.observe(RESPONSE, 0, bytes([len(data)]) + data.ljust(7, b'\0'), now)
      pending = self.session.update(now, healthy=True, request=request,
                                    direction='left', driver_override=driver)
      self.effects.extend(item.address for item in pending)

  def assert_no_indicator(self):
    assert not set(SPAS).intersection(self.effects)


def test_reported_replies_with_simulated_timing():
  trial = Replay()
  trial.step(reply='5003003201f4')
  trial.step(reply='7f2822')
  assert trial.session.reason == 'ecu_rejected'
  trial.step(reply='7f2822')
  trial.step(45)
  assert trial.session.state == 'restore_default'
  trial.step(reply='5001003201f4')
  trial.step()
  assert trial.session.state == 'idle'
  assert trial.session.restore_ack and trial.session.stock_resumed
  trial.assert_no_indicator()


@pytest.mark.parametrize(('advance', 'reason'), [(False, 'session_timeout'), (True, 'disable_timeout')])
def test_timeout_never_activates_indicator(advance, reason):
  trial = Replay()
  if advance:
    trial.step(reply='5003003201f4')
  trial.step(45)
  assert trial.session.reason == reason
  trial.assert_no_indicator()


def test_positive_ack_with_stock_still_present():
  trial = Replay()
  trial.step(reply='5003003201f4')
  trial.step(reply='6803')
  trial.step(45)
  assert trial.session.reason == 'ecu_not_quiet'
  trial.assert_no_indicator()


@pytest.mark.parametrize('missing', ['ack', 'stock'])
def test_unconfirmed_restoration_stays_locked(missing):
  trial = Replay()
  trial.step(driver=True)
  assert trial.session.reason == 'driver_override'
  for _ in range(3):
    trial.step(45, stock=missing == 'ack')
    if missing == 'stock':
      trial.step(stock=False, reply='5001003201f4')
    trial.step(150, stock=missing == 'ack')
  assert trial.session.state == 'failed'
  assert trial.session.reason == 'restore_unconfirmed'
  old_count = len(trial.effects)
  trial.step(22, request=None)
  trial.step(request='new_trial')
  assert len(trial.effects) == old_count
  trial.assert_no_indicator()


def test_driver_override_while_waiting_for_stock_silence():
  trial = Replay()
  trial.step(reply='5003003201f4')
  trial.step(reply='6803', stock=False)
  trial.step(5, stock=False)
  trial.step(driver=True, stock=False)
  assert trial.session.reason == 'driver_override'
  trial.assert_no_indicator()


def test_uds_identity_and_dtc_decoding():
  assert decode_reply(bytes.fromhex('7f2822')) == {
    'kind': 'negative', 'service': 0x28, 'nrc': 0x22, 'name': 'conditions_not_correct'}
  assert decode_reply(bytes.fromhex('62f1893132')) == {'kind': 'read_data', 'did': 'f189', 'data_hex': '3132'}
  assert decode_reply(bytes.fromhex('5902ff12345608')) == {
    'kind': 'dtc_status', 'availability_mask': 0xff, 'records': [{'code_hex': '123456', 'status': 8}]}
  assert decode_reply(bytes.fromhex('5902ff'))['records'] == []
  for value in ('', '7f28', '62f189', '5902ff1234', '5003'):
    assert decode_reply(bytes.fromhex(value)) == {'kind': 'unclassified'}


def test_passive_scan_uses_only_valid_rx_on_selected_bus():
  def event(kind, valid=True, **data):
    return SimpleNamespace(which=lambda: kind, valid=valid, logMonoTime=10**9, **data)

  response = SimpleNamespace(address=RESPONSE, src=0, dat=bytes.fromhex('037f282200000000'))
  wrong_bus = SimpleNamespace(address=RESPONSE, src=1, dat=response.dat)
  events = [event('can', can=[response, wrong_bus]), event('can', False, can=[response]),
            event('sendcan', sendcan=[response])]
  result = summarize_rlog(events, 0)
  assert result['counts']['can_events'] == 1
  assert result['diagnostic_frame_counts'] == {'negative:28:22': 1}


def test_recorded_firmware_matches_parking_ecu_and_deduplicates():
  record = SimpleNamespace(ecu='parkingAdas', address=0x7b1, bus=0, subAddress=0,
                           responseAddress=RESPONSE, request=[bytes.fromhex('22f110')],
                           fwVersion=bytes.fromhex('f1101234'))
  unrelated = SimpleNamespace(**(vars(record) | {'bus': 1}))
  unknown_endpoint = SimpleNamespace(**(vars(record) | {'responseAddress': 0x700}))
  cp = SimpleNamespace(carFingerprint='HYUNDAI_IONIQ_5', carFw=[record, record, unrelated, unknown_endpoint])
  event = SimpleNamespace(which=lambda: 'carParams', valid=True, carParams=cp)
  assert summarize_rlog([event], 0)['recorded_firmware'] == [
    {'response_address': RESPONSE, 'request_hex': ['22f110'], 'version_hex': 'f1101234'}]
