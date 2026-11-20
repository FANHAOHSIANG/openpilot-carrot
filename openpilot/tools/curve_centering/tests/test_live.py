import json
import threading
from http.server import ThreadingHTTPServer
import pytest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from openpilot.tools.curve_centering.live import Snapshot, make_handler
from openpilot.tools.curve_centering.observer import Config


class TestLive:
  def test_snapshot_bounded_and_stale(self):
    snapshot = Snapshot(Config())
    assert snapshot.get()['age_s'] is None
    for i in range(650):
      snapshot.add({'t': float(i), 'eligible': False, 'reasons': ['test'], 'geometry': None, 'findings': []})
    assert len(snapshot.get()['rows']) == 600
    snapshot.last_received -= 2
    assert snapshot.get()['age_s'] > 2

  def test_get_only_http_contract(self):
    snapshot = Snapshot(Config())
    server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(snapshot))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{server.server_port}'
    try:
      with urlopen(url + '/snapshot', timeout=2) as response:
        assert response.headers['Cache-Control'] == 'no-store'
        assert json.load(response)['mode'] == 'observe_only'
      with urlopen(url, timeout=2) as response:
        assert '過彎置中研究台' in response.read().decode()
      for request, code in ((url + '/anything', 404), (Request(url + '/snapshot', data=b'{}', method='POST'), 501)):
        with pytest.raises(HTTPError) as error:
          urlopen(request, timeout=2)
        assert error.value.code == code
    finally:
      server.shutdown()
      server.server_close()
      thread.join(timeout=2)
