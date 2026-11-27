"""Read-only, normalized CSV trace audit; never generates control commands."""
import csv
import json
import math
import sys


def number(row, key):
    try:
        value = float(row[key])
        return value if math.isfinite(value) else None
    except (KeyError, TypeError, ValueError):
        return None


def audit(rows):
    events = []
    previous = None
    for row in rows:
        t = number(row, 't')
        if t is None:
            previous = None
            continue
        if previous is not None:
            dt = t - number(previous, 't')
            if 0 < dt <= 0.5:
                def pair(key):
                    return number(previous, key), number(row, key)
                def emit(kind, **details):
                    events.append(dict(t=t, kind=kind, **details))
                old, new = pair('lat_active')
                if old == 1 and new == 0:
                    emit('lateral_deactivated')
                old, new = pair('steer_request')
                if old == 1 and new == 0:
                    emit('request_fell', angle_deg=number(row, 'steering_angle_deg'))
                old, new = pair('reserve_ceiling')
                if old is not None and new is not None and new < old:
                    wheels = [number(row, 'wheel_' + w + '_kph') for w in ('fl', 'fr', 'rl', 'rr')]
                    emit('reserve_ceiling_fell', old=old, new=new, reason=row.get('reserve_reason') or None,
                         wheel_spread_kph=max(wheels)-min(wheels) if None not in wheels else None)
                old, new = pair('desired_kph')
                if old is not None and new is not None and old != new and 'pre' in (previous.get('source'), row.get('source')):
                    a0, a1 = pair('a_ego_mps2')
                    emit('pre_target_changed', old=old, new=new, source_before=previous.get('source'), source_after=row.get('source'),
                         measured_jerk_mps3=(a1-a0)/dt if a0 is not None and a1 is not None else None)
        previous = row
    return events


if __name__ == '__main__':
    with open(sys.argv[1], newline='') as file:
        print(json.dumps(audit(csv.DictReader(file)), ensure_ascii=False, allow_nan=False, indent=2))
