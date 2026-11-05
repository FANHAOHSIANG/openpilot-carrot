import json
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from c4_carstate_bridge import StateCache, handler

class BridgeTests(unittest.TestCase):
    def test_authentication_and_stale_values(self):
        cache = StateCache()
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler(cache, 'testtoken12345678901234'))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f'http://127.0.0.1:{server.server_port}/carstate'
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(url)
            self.assertEqual(error.exception.code, 401)
            request = urllib.request.Request(url, headers={'Authorization': 'Bearer testtoken12345678901234'})
            with urllib.request.urlopen(request) as result:
                self.assertEqual(json.load(result), {'valid': False})
            cache.publish({'speed':1.0, 'accel':0.0, 'brake':False, 'gear':'drive', 'left':False, 'right':False})
            with urllib.request.urlopen(request) as result:
                self.assertEqual(json.load(result)['gear'], 'drive')
            with cache.lock:
                cache.updated = time.monotonic() - 1
            with urllib.request.urlopen(request) as result:
                self.assertEqual(json.load(result), {'valid':False})
        finally:
            server.shutdown(); server.server_close(); thread.join()

if __name__ == '__main__': unittest.main()
