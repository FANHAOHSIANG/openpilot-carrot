from openpilot.tools.curve_centering.export_shadow import extract


def test_export_filters_other_events_and_private_context():
  assert extract({'msg': 'ordinary message'}) is None
  assert extract({'msg': {'event': 'unrelated'}}) is None
  record = {'ctx': {'dongle_id': 'private'}, 'host': 'private', 'msg': {
    'event$s': 'curve_centering_shadow', 'vehicle_output$b': False,
    'now_ns$i': 123, 'reasons$a': ['observer_gate'], 'unknown_private': 'private'}}
  assert extract(record) == {'event': 'curve_centering_shadow', 'vehicle_output': False,
                             'now_ns': 123, 'reasons': ['observer_gate']}


def test_export_native_log_message_and_stop_reason():
  assert extract('{"msg":{"event":"curve_centering_shadow_stopped","reason":"transport_TimeoutError"}}') == {
    'event': 'curve_centering_shadow_stopped', 'reason': 'transport_TimeoutError'}
