"""Manually launched read-only observer. Not registered with manager/process_config."""

import argparse
from collections import deque
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time

from .observer import Config, Observer, SERVICES
from .replay import summarize
from .report import render_report


class Snapshot:
  def __init__(self, config):
    self.config = config
    self.rows = deque(maxlen=600)  # Bounded ~30 s at 20 Hz.
    self.last_received = None
    self.started = None
    self.lock = threading.Lock()

  def add(self, row):
    with self.lock:
      if self.started is None:
        self.started = row['t']
      row = dict(row, source='即時觀察', relative_s=row['t'] - self.started)
      self.rows.append(row)
      self.last_received = time.monotonic()

  def get(self):
    with self.lock:
      rows = list(self.rows)
      age = None if self.last_received is None else time.monotonic() - self.last_received
    return {'mode': 'observe_only', 'rows': rows, 'summary': summarize(rows), 'sources': [], 'episodes': [], 'config': asdict(self.config), 'age_s': age}


def make_handler(snapshot):
  class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
      if self.path not in ('/', '/snapshot'):
        self.send_error(404)
        return
      report = snapshot.get()
      content = json.dumps(report, ensure_ascii=False, allow_nan=False) if self.path == '/snapshot' else render_report(report, live=True)
      data = content.encode('utf-8')
      self.send_response(200)
      self.send_header('Content-Type', 'application/json; charset=utf-8' if self.path == '/snapshot' else 'text/html; charset=utf-8')
      self.send_header('Cache-Control', 'no-store')
      self.send_header('X-Content-Type-Options', 'nosniff')
      self.send_header('Content-Length', str(len(data)))
      self.end_headers()
      self.wfile.write(data)

    def log_message(self, *args):
      pass

  return Handler


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--host', default='127.0.0.1', help='Default loopback; explicitly use 0.0.0.0 for trusted local-network viewing')
  parser.add_argument('--port', type=int, default=8766)
  parser.add_argument('--output', type=Path, help='Optional JSONL recording; local file only')
  parser.add_argument('--duration', type=float, default=300, help='Observation duration in seconds (default 5 minutes)')
  parser.add_argument('--vehicle-center-y', type=float)
  parser.add_argument('--vehicle-width', type=float)
  args = parser.parse_args()
  if not 0 < args.duration <= 86400:
    parser.error('--duration must be in (0, 86400]')
  from openpilot.cereal import messaging

  config = Config(vehicle_center_y_m=args.vehicle_center_y, vehicle_width_m=args.vehicle_width)
  observer, snapshot = Observer(config), Snapshot(config)
  sm = messaging.SubMaster(list(SERVICES), poll='lateralPlan')
  # Open before launching the HTTP thread; file collisions must not leak a server.
  output = args.output.open('x', encoding='utf-8') if args.output else None
  try:
    server = ThreadingHTTPServer((args.host, args.port), make_handler(snapshot))
  except Exception:
    if output:
      output.close()
    raise
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  start = time.monotonic()
  print(f'Observation only: http://{args.host}:{args.port} — no control or parameter writes', flush=True)
  try:
    while time.monotonic() - start < args.duration:
      sm.update(100)
      records = [
        {'kind': k, 'mono_ns': int(sm.logMonoTime[k]), 't': sm.logMonoTime[k] / 1e9, 'valid': bool(sm.valid[k] and sm.alive[k]), 'data': sm[k].to_dict()}
        for k in SERVICES
        if sm.updated[k]
      ]
      for record in sorted(records, key=lambda r: r['mono_ns']):
        row = observer.feed(record)
        if row is not None:
          snapshot.add(row)
          if output:
            output.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
    return 0
  except KeyboardInterrupt:
    return 0
  finally:
    if output:
      output.close()
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


if __name__ == '__main__':
  raise SystemExit(main())
