import json

from openpilot.tools.curve_centering.process_bench import phase
from openpilot.tools.curve_centering.process_bench_summary import distribution, summarize


def test_tails_are_reported_even_when_median_passes():
  stats = distribution([1_000_000]*99 + [25_000_000])
  assert stats['median_ms'] == 1
  assert stats['max_ms'] == 25
  assert stats['over_10ms'] == stats['over_15ms'] == 1
  assert distribution([]) is None


def test_source_and_receiver_delays_are_distinct_and_missing_not_fabricated(tmp_path):
  publications = [{'at': 7., 'message_ns': 10_000_000, 'publish_end_ns': 11_000_000, 'input_ns': 0,
                       'lat_active': False, 'state_wall_ns': 2_000_000, 'dropped': 0, 'monitor_failed': False, 'thread_alive': False},
                  {'at': 7.02, 'message_ns': 30_000_000, 'publish_end_ns': 31_000_000, 'input_ns': 20_000_000,
                       'lat_active': True, 'state_wall_ns': 3_000_000, 'dropped': 0, 'monitor_failed': False, 'thread_alive': False}]
  (tmp_path/'child.json').write_text(json.dumps({'publications': publications, 'captures': [], 'worker': [], 'worker_stopped': []}))
  (tmp_path/'receiver.json').write_text(json.dumps({'received': [{'message_ns': 10_000_000, 'received_ns': 16_000_000}], 'sent': [0,20_000_000]}))
  row = summarize(tmp_path)['phases'][0]
  assert row['publication_interval']['max_ms'] == 20
  assert row['input_to_publish']['max_ms'] == 11
  assert row['input_to_receiver']['max_ms'] == 16
  assert row['unreceived'] == 1
  assert row['lat_active'] == 1


def test_faults_and_recovery_have_separate_windows():
  assert [phase(t) for t in (6,12,16,20,24,28,32,36)] == [
    'nominal','gil_load','after_gil','slow_worker','after_overflow','closed','recreated','worker_exception']
