"""Read-only audit of historical Carrot curve HTML or exported CSV.
Does not connect to a vehicle, propose speeds, or change control parameters.
"""
import argparse
import base64
import csv
import io
import json
import math
import re
from pathlib import Path


def load_trace(path):
    if path.suffix.lower() == '.csv':
        return list(csv.DictReader(io.StringIO(path.read_text(encoding='utf-8-sig'))))
    html = path.read_text(encoding='utf-8')
    for encoded in re.findall(r'base64,([A-Za-z0-9+/=]+)', html):
        raw = base64.b64decode(encoded, validate=True)
        if raw.startswith(b't,seg,sec,time,speed,'):
            return list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    raise ValueError('No recognized embedded curve trace')


def finite(row, name):
    try:
        value = float(row[name])
        return value if math.isfinite(value) else None
    except (ValueError, TypeError, KeyError):
        return None


def active(row):
    return all(str(row.get(key)).lower() == want for key, want in
               [('longActive', 'true'), ('gas', 'false'), ('brake', 'false')])


def audit(rows):
    result = {'samples': len(rows), 'raw_steps': 0, 'capped_steps': 0,
              'active_steps': [], 'source_counts': {}, 'missing_torque_fields': []}
    for key in ('latActive', 'steerRequest', 'reserveCeiling', 'wheelSpeeds'):
        if not any(row.get(key) not in (None, '') for row in rows):
            result['missing_torque_fields'].append(key)
    for row in rows:
        source = row.get('src', '')
        result['source_counts'][source] = result['source_counts'].get(source, 0) + 1
    for old, new in zip(rows, rows[1:]):
        if not old.get('seg') or old.get('seg') != new.get('seg'):
            continue
        values = [finite(r, k) for r in (old, new) for k in ('t', 'desired', 'set')]
        if None in values:
            continue
        t0, raw0, set0, t1, raw1, set1 = values
        dt = t1 - t0
        if not 0 < dt <= 0.25:
            continue
        if abs(raw1 - raw0) >= 10:
            result['raw_steps'] += 1
        cap0, cap1 = min(raw0, set0), min(raw1, set1)
        if abs(cap1 - cap0) < 10:
            continue
        result['capped_steps'] += 1
        if not (active(old) and active(new)):
            continue
        result['active_steps'].append({'time': new.get('time'), 'dt_s': dt,
          'source_before': old.get('src'), 'source_after': new.get('src'),
          'cap_before_kph': cap0, 'cap_after_kph': cap1,
          'manual_set_before_kph': set0, 'manual_set_after_kph': set1,
          'vehicle_speed_kph': finite(new, 'speed'),
          'target_accel_before': finite(old, 'aTarget'), 'target_accel_after': finite(new, 'aTarget')})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(load_trace(args.trace)), ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
