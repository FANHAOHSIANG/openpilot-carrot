from types import SimpleNamespace as NS

import pytest

from tools.jetlink.spas_check import Monitor, health, parked
from opendbc.car.hyundai.spas import checksum, frame


def stock(m, start=10., bus=0):
  for i in range(10):
    for address in (0x165, 0x16A):
      value = frame(address, i, None, bus)
      m.observe(address, value.dat, bus, start+i*.02, start+i*.02)


def stalk():
  data = bytearray.fromhex('0030300000000000')
  crc = 0
  for byte in data[1:]:
    crc ^= byte
    for _ in range(8):
      crc = ((crc << 1) ^ (0x1d if crc & 0x80 else 0)) & 255
  data[0] = crc ^ 0x65
  return data


def test_stock_crc_counters_and_stale_expiry():
  m = Monitor(0, checksum)
  stock(m)
  assert m.ready(10.19)
  assert not m.ready(10.29)
  data = bytearray(frame(0x165, 10, None, 0).dat)
  data[4] ^= 1
  m.observe(0x165, data, 0, 10.2, 10.2)
  assert not m.ready(10.2)
  assert m.counts['0x165_invalid'] == 1


@pytest.mark.parametrize('bad', ['bus', 'future', 'old', 'duplicate', 'counter_gap'])
def test_no_false_readiness(bad):
  m = Monitor(0, checksum)
  for i in range(10):
    for address in (0x165, 0x16A):
      msg = frame(address, i if bad != 'counter_gap' else i*2, None, 0)
      stamp = 10.+i*.02
      m.observe(address, msg.dat, 1 if bad == 'bus' else 0,
                10. if bad == 'duplicate' else stamp+.2 if bad == 'future' else stamp,
                stamp+.2 if bad == 'old' else stamp)
  assert not m.ready(10.18)


def test_neutral_requires_fresh_three_stalk_frames_and_no_signal():
  m = Monitor(0, checksum)
  stock(m)
  for stamp in (10., 10.05):
    m.observe(0x3C1, stalk(), 0, stamp, stamp)
  assert not m.neutral(10.18)
  m.observe(0x3C1, stalk(), 0, 10.1, 10.1)
  assert m.neutral(10.18)
  value = frame(0x16A, 10, 'left', 0)
  m.observe(0x16A, value.dat, 0, 10.2, 10.2)
  assert not m.neutral(10.2)


def messages():
  class Messages(dict):
    pass
  p = NS(controlsAllowed=False, safetyTxBlocked=0)
  for i in range(3):
    setattr(p, f'canState{i}', NS(busOff=False, errorWarning=False, errorPassive=False,
      totalErrorCnt=0, busOffCnt=0, totalTxLostCnt=0, totalRxLostCnt=0))
  sm = Messages(carState=NS(canValid=True, vEgo=0., standstill=True, gearShifter='park',
    gasPressed=False, brakePressed=False, blinkerLever=0), carControl=NS(latActive=False, longActive=False),
    selfdriveState=NS(enabled=False, active=False), pandaStates=[p])
  sm.valid = dict.fromkeys(sm, True)
  sm.alive = dict.fromkeys(sm, True)
  sm.recv_time = dict.fromkeys(sm, 10.)
  return sm


@pytest.mark.parametrize('bad', ['moving', 'nan', 'drive', 'pedal', 'lat', 'long', 'enabled', 'stale', 'future', 'invalid', 'panda', 'bus_error', 'missing_health'])
def test_parked_guard_rejects_unready_state(bad):
  sm = messages()
  assert parked(sm, 10.01)
  if bad == 'moving': sm['carState'].vEgo = .1
  if bad == 'nan': sm['carState'].vEgo = float('nan')
  if bad == 'drive': sm['carState'].gearShifter = 'drive'
  if bad == 'pedal': sm['carState'].gasPressed = True
  if bad == 'lat': sm['carControl'].latActive = True
  if bad == 'long': sm['carControl'].longActive = True
  if bad == 'enabled': sm['selfdriveState'].enabled = True
  if bad == 'stale': sm.recv_time['carControl'] = 9.
  if bad == 'future': sm.recv_time['carControl'] = 11.
  if bad == 'invalid': sm.valid['carState'] = False
  if bad == 'panda': sm['pandaStates'] = []
  if bad == 'bus_error': sm['pandaStates'][0].canState2.errorWarning = True
  if bad == 'missing_health': del sm['pandaStates'][0].canState2
  assert not parked(sm, 10.01)


def test_health_includes_all_controllers_and_blocked_count():
  sm = messages()
  baseline = health(sm['pandaStates'])
  sm['pandaStates'][0].canState2.totalErrorCnt += 1
  assert health(sm['pandaStates']) != baseline
  sm['pandaStates'][0].canState2.totalErrorCnt -= 1
  sm['pandaStates'][0].safetyTxBlocked += 1
  assert health(sm['pandaStates']) != baseline


def test_reply_is_bus_and_time_bound_and_bounded():
  m = Monitor(0, checksum)
  for _ in range(40):
    m.observe(0x7B9, bytes.fromhex('0250030000000000'), 0, 10., 10.)
  assert len(m.replies) == 32
  m.observe(0x7B9, bytes.fromhex('0268030000000000'), 1, 10., 10.)
  m.observe(0x7B9, bytes.fromhex('0268030000000000'), 0, 9., 10.)
  assert all(value == '5003' for _, value in m.replies)


@pytest.fixture
def harness(monkeypatch):
  import sys
  import types
  import openpilot.cereal as cereal
  from tools.jetlink import spas_check as tool
  from opendbc.car.hyundai.values import HyundaiFlags, HyundaiSafetyFlags
  clock = [10.]
  monkeypatch.setattr(tool, 'time', NS(monotonic=lambda: clock[0], sleep=lambda dt: clock.__setitem__(0, clock[0]+dt)))
  sm = messages()
  sm['carState'].leftBlinker = sm['carState'].rightBlinker = False
  sm['carState'].leftBlinkerStalkCount = sm['carState'].rightBlinkerStalkCount = 0
  sm['pandaStates'][0].safetyModel = 'hyundaiCanfd'
  sm['pandaStates'][0].safetyParam = HyundaiSafetyFlags.CANFD_SPAS_BLINKERS.value
  cp = cereal.car.CarParams.new_message(brand='hyundai', carFingerprint='HYUNDAI_IONIQ_5', passive=False,
    flags=(HyundaiFlags.CANFD | HyundaiFlags.CANFD_SPAS_BLINKERS).value)
  values = {'AutoBlinkerControl': 0, 'CanfdBlinkerTest': 0}
  writes, ticks = [], [0]
  fail = [False]
  def put(key, value):
    values[key] = value
    writes.append((key, value))
  params = NS(get=lambda key: cp.to_bytes(), get_int=lambda key: values[key],
    get_bool=lambda key: True, put_int=put)
  pmod = types.ModuleType('openpilot.common.params')
  pmod.Params = lambda: params
  monkeypatch.setitem(sys.modules, pmod.__name__, pmod)
  canmod = types.ModuleType('opendbc.car.hyundai.hyundaicanfd')
  canmod.CanBus = lambda cp: NS(ECAN=0)
  monkeypatch.setitem(sys.modules, canmod.__name__, canmod)
  def update(_):
    sm.recv_time = dict.fromkeys(sm, clock[0])
    sm['carState'].leftBlinker = values['CanfdBlinkerTest'] == 1
    sm['carState'].rightBlinker = values['CanfdBlinkerTest'] == 2
  sm.update = update
  def drain(*args, **kwargs):
    if fail[0] and values['CanfdBlinkerTest']:
      raise OSError('injected observer failure')
    ticks[0] += 1
    packets = []
    for address in (0x165, 0x16A):
      f = frame(address, ticks[0] % 256, None, 0)
      packets.append(NS(address=address, dat=f.dat, src=0))
    packets.append(NS(address=0x3C1, dat=stalk(), src=0))
    if values['CanfdBlinkerTest']:
      for reply in ('0250030000000000', '0268030000000000'):
        packets.append(NS(address=0x7B9, dat=bytes.fromhex(reply), src=0))
    elif writes:
      packets.append(NS(address=0x7B9, dat=bytes.fromhex('0250010000000000'), src=0))
    return [NS(valid=True, logMonoTime=int(clock[0]*1e9), can=packets)]
  # Deliberately no publisher API: default and test must use existing Params only.
  messaging = NS(SubMaster=lambda services: sm, sub_sock=lambda *a, **kw: object(), drain_sock=drain)
  monkeypatch.setattr(cereal, 'messaging', messaging, raising=False)
  return tool, values, writes, fail


def test_default_observation_never_writes_params(harness):
  tool, _, writes, _ = harness
  assert tool.run(NS(test=None)) == 0
  assert writes == []


@pytest.mark.parametrize('direction,value', [('left', 1), ('right', 2)])
def test_explicit_test_uses_only_existing_mode_then_cancels(harness, direction, value):
  tool, _, writes, _ = harness
  assert tool.run(NS(test=direction)) == 0
  assert writes == [('CanfdBlinkerTest', value), ('CanfdBlinkerTest', 0)]


def test_observer_exception_always_cancels_owned_test(harness):
  tool, _, writes, fail = harness
  fail[0] = True
  with pytest.raises(OSError):
    tool.run(NS(test='left'))
  assert writes == [('CanfdBlinkerTest', 1), ('CanfdBlinkerTest', 0)]


def test_automatic_mode_blocks_test_without_writes(harness):
  tool, values, writes, _ = harness
  values['AutoBlinkerControl'] = 2
  with pytest.raises(RuntimeError, match='isolated test'):
    tool.run(NS(test='left'))
  assert writes == []
