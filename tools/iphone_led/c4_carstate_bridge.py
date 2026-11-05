#!/usr/bin/env python3
"""Read-only, token-protected C4 carState bridge for an iPhone on a local network."""
import argparse
import hmac
import json
import math
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class StateCache:
    def __init__(self):
        self.lock = threading.Lock()
        self.state = None
        self.updated = 0.0

    def publish(self, state):
        with self.lock:
            self.state = state
            self.updated = time.monotonic()

    def read(self):
        with self.lock:
            age = time.monotonic() - self.updated
            if self.state is None or age > 0.7:
                return {'valid': False}
            return {'valid': True, **self.state}

def handler(cache, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            if self.path != '/carstate':
                self.send_error(404)
                return
            supplied = self.headers.get('Authorization', '')
            if not hmac.compare_digest(supplied, 'Bearer ' + token):
                self.send_error(401)
                return
            body = json.dumps(cache.read(), allow_nan=False, separators=(',', ':')).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    return Handler

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=18765)
    args = parser.parse_args()
    token = os.environ.get('CARROT_LED_TOKEN', '')
    if len(token) < 20 or len(token) > 128 or not token.isascii() or not token.isalnum():
        raise SystemExit('CARROT_LED_TOKEN must be 20–128 ASCII letters or numbers')
    from openpilot.cereal import messaging
    cache = StateCache()
    server = ThreadingHTTPServer(('0.0.0.0', args.port), handler(cache, token))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f'Read-only C4 LED bridge listening on port {args.port}', flush=True)
    sm = messaging.SubMaster(['carState'])
    try:
        while True:
            sm.update(100)
            if not (sm.updated['carState'] and sm.valid['carState'] and sm.alive['carState']):
                continue
            cs = sm['carState']
            speed, accel = float(cs.vEgo), float(cs.aEgo)
            if math.isfinite(speed) and math.isfinite(accel):
                cache.publish({'speed': speed, 'accel': accel, 'brake': bool(cs.brakePressed),
                               'left': bool(cs.leftBlinker), 'right': bool(cs.rightBlinker),
                               'gear': str(cs.gearShifter)})
    finally:
        server.shutdown()
        server.server_close()

if __name__ == '__main__':
    main()
