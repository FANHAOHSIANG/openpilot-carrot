#!/usr/bin/env python3
"""Offline, deterministic replay of HUD projection using four Navipilot exports.

Run with Python 3 and numpy from an openpilot checkout. This runs the real
cluster_live HUD methods with simulated SubMaster data and a monotonic clock.
The phone exports contain telemetry snapshots rather than raw cereal messages.
No connections are opened. Output contains aggregate counts and distances only.
"""

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
import zipfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

FIXTURES = {
    "1794547153013": "8335e4a712babe61d447e7ec3a33bca35142383fc68ada371e5e40f3884f29f3",
    "1794547554785": "e667da66ad5dcd369d3d3f713cd74a41c8edd666c73e1a7c0fa2b8f6f64aa3b2",
    "1794560921751": "35be69439b10904231575277681dece2faecedc62b42853dea745da39ebb4999",
    "1794580678532": "3f1310cad326e38d22b8006452ce2d4e3c97adaf6be5ff4c3cd2cfe417f1b360",
}
METERS_PER_DEGREE = 111133.0


def gcj02(lat, lon):
    """Diagnostic only. Compare the untagged route with the GPS in GCJ-02."""
    x, y = lon - 105, lat - 35
    pi = math.pi
    sin = math.sin
    common = 20 * (sin(6 * x * pi) + sin(2 * x * pi)) * 2 / 3
    dlat = -100 + 2*x + 3*y + .2*y*y + .1*x*y + .2*math.sqrt(abs(x)) + common
    dlat += (20*sin(y*pi) + 40*sin(y*pi/3)) * 2/3 + (160*sin(y*pi/12) + 320*sin(y*pi/30)) * 2/3
    dlon = 300 + x + 2*y + .1*x*x + .1*x*y + .1*math.sqrt(abs(x)) + common
    dlon += (20*sin(x*pi) + 40*sin(x*pi/3)) * 2/3 + (150*sin(x*pi/12) + 300*sin(x*pi/30)) * 2/3
    radians = math.radians(lat)
    a, e = 6378245.0, .006693421622965943
    factor = 1 - e * sin(radians)**2
    lat_scale = a * (1 - e) / (factor * math.sqrt(factor))
    lon_scale = a / math.sqrt(factor) * math.cos(radians)
    return lat + math.degrees(dlat / lat_scale), lon + math.degrees(dlon / lon_scale)


def distance_to_route(lat, lon, points):
    lon_scale = METERS_PER_DEGREE * math.cos(math.radians(lat))
    local = [((p.latitude - lat) * METERS_PER_DEGREE, (p.longitude - lon) * lon_scale) for p in points]
    best = math.inf
    for (ax, ay), (bx, by) in zip(local, local[1:]):
        dx, dy = bx - ax, by - ay
        length2 = dx*dx + dy*dy
        if length2 < 1:
            continue
        ratio = min(1., max(0., -(ax*dx + ay*dy) / length2))
        best = min(best, math.hypot(ax + ratio*dx, ay + ratio*dy))
    return best


def frames(path, expected_hash):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
        raise ValueError(f"Fixture SHA-256 mismatch: {path.name}")
    with zipfile.ZipFile(path) as archive:
        names = sorted(
            (name for name in archive.namelist() if re.fullmatch(r"events\d+\.jsonl", name)),
            key=lambda name: int(name[6:-6]),
        )
        rows = []
        for name in names:
            with archive.open(name) as stream:
                rows.extend(row for line in stream if (row := json.loads(line))["event"] == "c4_telemetry")
    return sorted(rows, key=lambda row: row["mono_ms"])


def live_source(module):
    # Instantiate only the HUD state used by the projection. The real __init__
    # creates live subscriptions, which are deliberately outside this replay.
    source = object.__new__(module.OpenpilotLiveSource)
    source._nav_route_coords = ()
    source._nav_route_received_t = 0.
    source._nav_route_id = 0
    source._nav_route_segment = None
    source._nav_route_filtered_anchor = None
    source._nav_route_anchor_t = 0.
    source._nav_route_last_path = ()
    source.sm = SubMaster()
    return source


class SubMaster(dict):
    def __init__(self):
        super().__init__()
        self.recv_time = {}
        self.valid = {}
        self.alive = {}


def run_recording(module, path, expected_hash):
    rows = frames(path, expected_hash)
    source = live_source(module)
    clock = SimpleNamespace(monotonic=lambda: 1.)
    original_clock = module.time
    module.time = clock
    reference = replace(module.standby_state(), model_path=(module.ModelPathPoint(0., 0.),))
    direct, corrected, jumps = [], [], []
    previous, previous_t, previous_route, next_heartbeat = None, None, None, 0.
    shown = fallback_errors = shape_errors = compatible = 0
    first_time = rows[0]["mono_ms"]
    route_id = 0
    try:
        for frame in rows:
            now = 1. + (frame["mono_ms"] - first_time) / 1000.
            clock.monotonic = lambda: now
            data = frame["data"]
            raw = data.get("carrotMan") or {}
            route = (data.get("carrotNavi") or {}).get("route") or {}
            polyline = route.get("polyline", []) if route.get("present") else []
            coordinates = tuple((p["latitude"], p["longitude"]) for p in polyline)
            route_key = (data["carrotNavi"].get("sessionId"), coordinates)
            points = [SimpleNamespace(latitude=lat, longitude=lon) for lat, lon in coordinates]
            if route_key != previous_route or now >= next_heartbeat:
                route_id += int(route_key != previous_route)
                source.sm["navRoute"] = SimpleNamespace(coordinates=points, carrotRouteId=route_id)
                source.sm.valid["navRoute"] = True
                source._apply_service_update("navRoute", now)
                next_heartbeat = now + 2.
            lat, lon, heading = (raw.get(key) for key in ("xPosLat", "xPosLon", "xPosAngle"))
            usable = all(isinstance(v, (int, float)) and math.isfinite(v) for v in (lat, lon, heading))
            usable = usable and abs(lat) <= 90 and abs(lon) <= 180 and bool(lat or lon)
            source.sm["carrotMan"] = SimpleNamespace(**raw)
            source.sm.valid["carrotMan"] = usable
            source.sm.alive["carrotMan"] = bool(raw)
            source.sm.recv_time["carrotMan"] = now
            state = source._with_external_nav_route(reference)
            visible = state is not reference
            fallback_errors += int(visible and (not usable or len(points) < 2))
            if usable and len(points) >= 2:
                distance = distance_to_route(lat, lon, points)
                shifted = distance_to_route(*gcj02(lat, lon), points)
                if math.isfinite(distance) and math.isfinite(shifted):
                    direct.append(distance)
                    corrected.append(shifted)
                    compatible += int(distance <= 12.)
                shown += int(visible)
                if visible:
                    projection = state.model_path
                    shape_errors += int(any(
                        not math.isfinite(p.forward_m) or not math.isfinite(p.lateral_m)
                        or not 0 <= p.forward_m <= 180 or abs(p.lateral_m) > 35
                        for p in projection
                    ) or any(b.forward_m <= a.forward_m for a, b in zip(projection, projection[1:])))
                    current = lateral_at(projection, 20.)
                    if current is not None and previous is not None and 0 < now - previous_t <= 1.:
                        jumps.append(abs(current - previous))
                    previous, previous_t = current, now
                else:
                    previous = previous_t = None
            else:
                previous = previous_t = None
            previous_route = route_key
    finally:
        module.time = original_clock
    offset_deltas = [a - b for a, b in zip(direct, corrected)]
    return {
        "id": path.stem.rsplit("-", 1)[-1], "telemetry": len(rows),
        "samples": len(direct), "shown": shown, "compatible": compatible,
        "direct_m": rounded_median(direct), "gcj_m": rounded_median(corrected),
        "offset_delta_m": rounded_median(offset_deltas),
        "max_jump_20m": round(max(jumps), 2) if jumps else None,
        "jump_pairs_20m": len(jumps), "fallback_errors": fallback_errors,
        "shape_errors": shape_errors,
    }


def lateral_at(points, distance):
    for a, b in zip(points, points[1:]):
        if a.forward_m <= distance <= b.forward_m:
            ratio = (distance - a.forward_m) / (b.forward_m - a.forward_m)
            return a.lateral_m + ratio * (b.lateral_m - a.lateral_m)
    return None


def rounded_median(values):
    return round(statistics.median(values), 2) if values else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, default=Path.cwd())
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--diagnostics", action="store_true", help="Print results without enforcing the merge gate")
    args = parser.parse_args()
    root = args.checkout.resolve()
    sys.path[:0] = [str(root / "openpilot/selfdrive/carrot/cluster"), str(root)]
    import cluster_live

    results = [
        run_recording(cluster_live, args.fixtures / f"Navipilot-TW-log-{key}.zip", digest)
        for key, digest in FIXTURES.items()
    ]
    failures = []
    for row in results:
        if row["fallback_errors"] or row["shape_errors"]:
            failures.append(f'{row["id"]}: invalid HUD output')
        if row["offset_delta_m"] is not None and row["offset_delta_m"] > 30:
            failures.append(f'{row["id"]}: route coordinate system needs source verification')
        elif row["compatible"] < 20 or row["shown"] < row["compatible"] * .65:
            failures.append(f'{row["id"]}: insufficient confirmed HUD coverage')
        if row["jump_pairs_20m"] and row["max_jump_20m"] > 5:
            failures.append(f'{row["id"]}: lateral frame-to-frame jump exceeds 5 m at 20 m')
    print(json.dumps({"recordings": results, "failures": failures}, indent=2))
    return 0 if args.diagnostics or not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
