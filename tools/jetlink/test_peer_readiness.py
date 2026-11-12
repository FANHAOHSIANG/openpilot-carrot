import pytest
from openpilot.selfdrive.modeld.jetlink.link import peer_ready


def status():
  return {'state': 'ready', 'updated': 10., 'peer': {'protocol': 3}, 'sha256': 'model',
              'telemetry': {'loaded': 'model'}, 'telemetry_updated': 9.}


def test_fresh_host_model_reply_allows_preparation():
  assert peer_ready(status(), 10.)


@pytest.mark.parametrize('patch', [{'telemetry_updated': 0}, {'telemetry_updated': 6.},
                                  {'telemetry_updated': 11.}, {'telemetry': None},
                                  {'telemetry': {}}, {'telemetry': {'loaded': None}},
                                  {'telemetry': {'loaded': 'other'}}, {'peer': {}},
                                  {'state': 'disconnected'}, {'updated': 6.}])
def test_daemon_heartbeat_cannot_replace_host_reply(patch):
  value = status()
  value.update(patch)
  assert not peer_ready(value, 10.)
