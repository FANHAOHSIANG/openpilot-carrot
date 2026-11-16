#!/usr/bin/env python3
"""Read-only bridge probe. Never prints the bearer token or vehicle values."""
import argparse
import http.client
import ipaddress
import json
import os
import statistics
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--seconds', type=int, default=30, choices=range(5, 181), metavar='5..180')
    parser.add_argument('--token-file', default='/data/iphone-led/token')
    args = parser.parse_args()
    address = ipaddress.ip_address(args.host)
    if not address.is_private or address.version != 4:
        parser.error('Use the local C4 IPv4 address')
    token = Path(args.token_file).read_text().strip()
    conn = http.client.HTTPConnection(args.host, 18765, timeout=1.5)
    samples, counts = [], {}
    deadline = time.monotonic() + args.seconds
    while time.monotonic() < deadline:
        started = time.monotonic()
        try:
            conn.request('GET', '/carstate', headers={'Authorization': 'Bearer ' + token, 'Cache-Control': 'no-cache'})
            reply = conn.getresponse()
            body = reply.read(8193)
            elapsed = (time.monotonic()-started)*1000
            if reply.status != 200:
                kind = f'HTTP {reply.status}'
            elif len(body)>8192:
                kind = 'oversized response'
            else:
                data = json.loads(body)
                kind = 'valid carState' if data.get('valid') is True else 'bridge replied without valid carState'
                samples.append(elapsed)
        except Exception as error:
            kind = type(error).__name__
            conn.close()
        counts[kind] = counts.get(kind, 0)+1
        time.sleep(max(0, 0.2-(time.monotonic()-started)))
    conn.close()
    report = {'seconds': args.seconds, 'responses': counts,
              'latency_ms': {'median': round(statistics.median(samples),1), 'max': round(max(samples),1)} if samples else None}
    if address.is_loopback:
        report['c4_load_average'] = os.getloadavg()
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
