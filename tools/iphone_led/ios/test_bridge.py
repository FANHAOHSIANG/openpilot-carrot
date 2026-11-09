import json
import http.client
import concurrent.futures
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from c4_carstate_bridge import StateCache, handler

class BridgeTests(unittest.TestCase):
    def test_three_clients_reuse_independent_connections(self):
        cache = StateCache()
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler(cache, 'testtoken12345678901234'))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        def client():
            conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=2)
            sock = None
            try:
                for _ in range(20):
                    conn.request('GET', '/carstate', headers={'Authorization':'Bearer testtoken12345678901234'})
                    reply = conn.getresponse()
                    self.assertEqual(reply.status, 200)
                    self.assertEqual(json.loads(reply.read()), {'valid':False})
                    self.assertFalse(reply.will_close)
                    if sock is None: sock = conn.sock
                    else: self.assertIs(conn.sock, sock)
            finally: conn.close()
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                for future in [pool.submit(client) for _ in range(3)]: future.result()
        finally:
            server.shutdown(); server.server_close(); thread.join()

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
            cache.publish({'speed':0.0, 'accel':0.0, 'brake':True, 'gear':'reverse', 'left':True, 'right':True})
            with urllib.request.urlopen(request) as result:
                reverse = json.load(result)
                self.assertTrue(reverse['valid'])
                self.assertEqual(reverse['gear'], 'reverse')
                self.assertTrue(reverse['left'] and reverse['right'])
            with cache.lock:
                cache.updated = time.monotonic() - 1
            with urllib.request.urlopen(request) as result:
                self.assertEqual(json.load(result), {'valid':False})
        finally:
            server.shutdown(); server.server_close(); thread.join()

if __name__ == '__main__': unittest.main()
