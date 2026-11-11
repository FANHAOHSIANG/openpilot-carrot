"""Offline OSM matcher/preview comparison, not a control or IPC replay.

Use the route's full cereal schema (with car.capnp and include/c++.capnp) and
an installed map cache. Compare --source phone with --source device, then
--source device --lane-width using the same logs and cache. Receive timestamps
are approximated by event publication timestamps. No CAN commands are sent.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
from types import SimpleNamespace

import capnp
import zstandard

from openpilot.selfdrive.carrot.gps_sources import GPSSources
from openpilot.selfdrive.carrot.osm_map import Road, RoadMatcher, TileStore, corridor_id
from openpilot.selfdrive.carrot.route_curve import RouteCurveSpeed


def replay(logs, schema_root, cache, source, lane_width):
  schema = capnp.load(str(schema_root / 'log.capnp'), imports=[str(schema_root)])
  store, matcher, tracker, gps_sources = TileStore(cache), RoadMatcher(), RouteCurveSpeed(), GPSSources()
  latest, counts, roads_without_width = {}, Counter(), {}
  next_match, points, status, allowance = 0., (), 'starting', 0.
  for path in sorted(logs):
    with path.open('rb') as stream, zstandard.ZstdDecompressor().stream_reader(stream) as reader:
      data = reader.read()
    events = []
    for event in schema.Event.read_multiple_bytes(data):
      kind = event.which()
      if kind in ('carrotMan', 'carState', 'modelV2', 'gpsLocationExternal'):
        events.append((event.logMonoTime / 1e9, kind, getattr(event, kind).to_dict(), event.valid))
    for now, kind, value, valid in sorted(events, key=lambda item: item[0]):
      latest[kind] = (now, value, valid)
      if kind != 'carrotMan' or not all(k in latest for k in ('carState', 'modelV2', 'gpsLocationExternal')):
        continue
      _, cs, _ = latest['carState']
      model_time, model, model_valid = latest['modelV2']
      gps_time, gps, gps_valid = latest['gpsLocationExternal']
      position, heading, fix_time = (value['xPosLon'], value['xPosLat']), value['xPosAngle'], value['positionFixMonoTime'] / 1e9
      if source == 'device':
        if gps_valid and gps['hasFix']:
          gps_sources.put('device', gps['latitude'], gps['longitude'], gps['bearingDeg'], gps['speed'], gps_time)
        else:
          gps_sources.remove('device')
        fix = gps_sources.device_preview(now, cs['vEgo'])
        position, heading, fix_time = ((fix.longitude, fix.latitude), fix.heading, fix.stamp) if fix else ((0., 0.), 0., -1.)
      if now >= next_match:
        next_match, allowance = now + .2, 0.
        if not 0 <= now - fix_time <= 1.5:
          points, status = (), 'stale_position'
        elif not 2 <= cs['vEgo'] <= 90:
          points, status = (), 'invalid_speed'
        else:
          roads = store.nearby(position)
          if not lane_width:
            # Retain immutable identities to preserve matcher caching behavior.
            roads_without_width = {id(r): roads_without_width.get(id(r), (r, Road(r.points, r.oneway))) for r in roads}
            roads = [roads_without_width[id(r)][1] for r in roads]
          points, status = matcher.match(roads, position, heading)
          allowance = matcher.lateral_allowance if lane_width else 0.
        tracker.set_route(points, ('osm', corridor_id(points)))
      near_model = SimpleNamespace(position=SimpleNamespace(x=model['position']['x'], y=model['position']['y']))
      result = tracker.update(now=now, position=position, heading=heading, position_time=fix_time,
                              model=near_model, model_time=model_time if model_valid else -1.,
                              v_ego=cs['vEgo'], a_ego=cs['aEgo'], speed_ratio=cs['vCluRatio'], lateral_allowance=allowance)
      counts[status + '/' + result.reason] += 1
  return dict(samples=sum(counts.values()), source=source, lane_width=lane_width, statuses=dict(counts))


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--schema-root', required=True, type=Path)
  parser.add_argument('--cache', required=True, type=Path)
  parser.add_argument('--source', choices=('phone', 'device'), required=True)
  parser.add_argument('--lane-width', action='store_true')
  parser.add_argument('logs', type=Path, nargs='+')
  args = parser.parse_args()
  print(json.dumps(replay(args.logs, args.schema_root, args.cache, args.source, args.lane_width), indent=2))
