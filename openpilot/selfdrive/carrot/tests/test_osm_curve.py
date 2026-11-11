import gzip
import io
import math
import tarfile

import numpy as np
import pytest

from openpilot.selfdrive.carrot.osm_curve import OsmCurveClient, fresh_request, read_message, valid_position, write_message
from openpilot.selfdrive.carrot.osm_map import (
  GROUPS, DownloadCancelled, Road, RoadMatcher, TileStore, corridor_id, covered, group_age, group_path,
  install_archive, schema, tile_bounds, tile_name,
)
from openpilot.selfdrive.carrot.osmd import OsmWorker
from openpilot.selfdrive.carrot.route_curve import RouteCurveSpeed
from openpilot.selfdrive.carrot.tests.test_route_curve import lonlat, road, run


def make_archive(path, roads=(), *, missing=False, bad_path=False):
  with tarfile.open(path, 'w:gz') as archive:
    for y in range(8):
      for x in range(8):
        if missing and x == y == 7:
          continue
        bounds = (24 + y / 4, 120 + x / 4, 24 + (y + 1) / 4, 120 + (x + 1) / 4)
        tile = schema().Offline.new_message(minLat=bounds[0], minLon=bounds[1], maxLat=bounds[2], maxLon=bounds[3], overlap=.001)
        # Duplicate overlapping ways intentionally: the graph must deduplicate
        # their edges instead of inventing forks at tile boundaries.
        ways = tile.init('ways', len(roads))
        for i, value in enumerate(roads):
          ways[i].id, ways[i].oneWay = i + 1, value.oneway
          ways[i].lanes = value.lanes
          ways[i].highwayClass = 'motorway' if value.motorway else 'unknown'
          nodes = ways[i].init('nodes', len(value.points))
          for n, (lon, lat) in zip(nodes, value.points, strict=True):
            n.longitude, n.latitude = float(lon), float(lat)
        data = tile.to_bytes_packed()
        name = '../../escape' if bad_path and x == y == 7 else 'offline/24/120/' + tile_name(bounds)
        info = tarfile.TarInfo(name)
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
  return path


@pytest.mark.parametrize('lat,lon', [(25.03, 121.56), (24.8, 120.97), (24.16, 120.65), (23., 120.2),
                                  (22.63, 120.3), (21.94, 120.8), (23.99, 121.6), (22.76, 121.14),
                                  (23.57, 119.57), (24.43, 118.32), (24.99, 119.45), (26.16, 119.95), (26.36, 120.49)])
def test_taiwan_mainland_and_outlying_island_coverage(lat, lon):
  assert covered(lat, lon)
  assert (math.floor(lat / 2) * 2, math.floor(lon / 2) * 2) in GROUPS


def test_unique_curve_without_navigation_reaches_real_speed_calculator():
  xy = road()
  points, status = RoadMatcher().match([Road(lonlat(xy))], lonlat((0, 0)), 90)
  assert status == 'road_matched'
  tracker = RouteCurveSpeed()
  tracker.set_route(points, corridor_id(points))
  result = run(tracker, xy)[-1]
  assert result.reason == 'matched'
  assert 70 < result.speed_kph < 90 and result.distance > 180


def test_fork_truncates_before_turn_even_if_main_road_has_more_points():
  xy = road()
  branch = np.array([(100, 0), (110, -20), (130, -40)])
  points, status = RoadMatcher().match([Road(lonlat(xy)), Road(lonlat(branch))], lonlat((0, 0)), 90)
  assert status == 'road_matched'
  assert points[-1] == pytest.approx(lonlat((100, 0)))
  tracker = RouteCurveSpeed()
  tracker.set_route(points, 1)
  assert run(tracker, xy)[-1].speed_kph == 250


def test_same_geometry_crossing_stops_at_intersection():
  xy = np.column_stack([np.arange(0, 205, 5), np.zeros(41)])
  cross = np.array([(100, -40), (100, 0), (100, 40)])
  points, _ = RoadMatcher().match([Road(lonlat(xy)), Road(lonlat(cross))], lonlat((0, 0)), 90)
  assert points[-1] == pytest.approx(lonlat((100, 0)))


def test_parallel_roads_are_ambiguous_and_not_shifted_to_fit():
  xy = road()
  points, status = RoadMatcher().match([Road(lonlat(xy)), Road(lonlat(xy + (0, 4)))], lonlat((0, 2)), 90)
  assert not points and status == 'ambiguous_road'


def test_oneway_direction_and_unique_way_continuation():
  xy = road()
  roads = [Road(lonlat(xy[:31]), True), Road(lonlat(xy[30:]), True)]
  points, status = RoadMatcher().match(roads, lonlat((0, 0)), 90)
  assert status == 'road_matched' and len(points) == len(xy)
  assert RoadMatcher().match(roads, lonlat((50, 0)), 270)[1] == 'off_road'
  assert RoadMatcher().match([Road(lonlat(xy))], lonlat((50, 0)), 270)[1] == 'road_matched'


def test_stable_corridor_id_across_vertices_and_moving_local_window():
  xy = np.column_stack([np.arange(-1000, 2005, 5), np.zeros(601)])
  matcher = RoadMatcher()
  ids = []
  for x in range(0, 75, 5):
    points, status = matcher.match([Road(lonlat(xy))], lonlat((x, 0)), 90)
    assert status == 'road_matched'
    ids.append(corridor_id(points))
  assert len(set(ids)) == 1


def test_cached_topology_keeps_current_heading_and_new_fork_checks():
  roads = [Road(lonlat(road()), True)]
  matcher = RoadMatcher()
  assert matcher.match(roads, lonlat((0, 0)), 90)[1] == 'road_matched'
  graph = matcher._graph
  assert matcher.match(roads, lonlat((5, 0)), 90)[1] == 'road_matched'
  assert matcher._graph is graph
  assert matcher.match(roads, lonlat((5, 0)), 270)[1] == 'off_road'
  branch = Road(lonlat(np.array([(100, 0), (110, -20), (130, -40)])))
  points, status = matcher.match(roads + [branch], lonlat((5, 0)), 90)
  assert matcher._graph is not graph
  assert status == 'road_matched' and points[-1] == pytest.approx(lonlat((100, 0)))


def test_topology_cache_expires_with_segment_window_or_replaced_tile():
  roads = [Road(lonlat(np.column_stack([np.arange(-1000, 2005, 5), np.zeros(601)])), True)]
  matcher = RoadMatcher()
  matcher.match(roads, lonlat((0, 0)), 90)
  graph = matcher._graph
  matcher.match(roads, lonlat((100, 0)), 90)
  assert matcher._graph is not graph
  replacement = Road(roads[0].points.copy(), False)
  assert matcher.match([replacement], lonlat((100, 0)), 270)[1] == 'road_matched'
  assert matcher.match([], lonlat((100, 0)), 90)[1] == 'no_roads'


def test_real_tile_format_atomic_install_and_cross_tile_query(tmp_path):
  archive = make_archive(tmp_path / 'good.tar.gz', [Road(lonlat(road()))])
  assert install_archive(archive, tmp_path / 'cache', (24, 120)) > 0
  store = TileStore(tmp_path / 'cache')
  roads = store.nearby(lonlat((0, 0)))
  assert len(store.cache) == 4  # exactly on both quarter-degree boundaries
  assert RoadMatcher().match(roads, lonlat((0, 0)), 90)[1] == 'road_matched'
  assert group_age(tmp_path / 'cache', (24, 120)) < 10


@pytest.mark.parametrize('fault', ['truncated', 'trailer', 'crc', 'missing', 'path', 'cancel'])
def test_bad_download_preserves_last_good_group(tmp_path, fault):
  root = tmp_path / 'cache'
  archive = make_archive(tmp_path / 'good.tar.gz')
  install_archive(archive, root, (24, 120))
  before = group_path(root, (24, 120)).read_bytes()
  bad = make_archive(tmp_path / 'bad.tar.gz', missing=fault == 'missing', bad_path=fault == 'path')
  data = bad.read_bytes()
  if fault == 'truncated':
    bad.write_bytes(data[:len(data) // 2])
  elif fault == 'trailer':
    bad.write_bytes(data[:-3])
  elif fault == 'crc':
    bad.write_bytes(data[:-8] + bytes([data[-8] ^ 255]) + data[-7:])
  with pytest.raises((ValueError, EOFError, gzip.BadGzipFile, tarfile.TarError, DownloadCancelled)):
    install_archive(bad, root, (24, 120), allowed=lambda: fault != 'cancel')
  assert group_path(root, (24, 120)).read_bytes() == before
  assert not list(root.glob('*.part'))


def test_missing_adjacent_tile_is_not_a_complete_corridor(tmp_path):
  archive = make_archive(tmp_path / 'good.tar.gz', [Road(lonlat(road()))])
  install_archive(archive, tmp_path / 'cache', (24, 120))
  import sqlite3
  with sqlite3.connect(group_path(tmp_path / 'cache', (24, 120))) as conn:
    conn.execute('DELETE FROM tiles WHERE name=?', (tile_name(tile_bounds(24.99, 120.99)),))
  with pytest.raises(ValueError, match='tile_missing'):
    TileStore(tmp_path / 'cache').nearby(lonlat((0, 0)))


def test_old_cache_and_out_of_coverage_do_not_yield_road(tmp_path):
  archive = make_archive(tmp_path / 'good.tar.gz')
  install_archive(archive, tmp_path / 'cache', (24, 120), fetched_at=1)
  store = TileStore(tmp_path / 'cache')
  with pytest.raises(ValueError, match='maps_missing_or_old'):
    store.nearby((121.55, 25.05))
  with pytest.raises(ValueError, match='outside_coverage'):
    store.nearby((139., 35.))


def client_input(now=10., **kwargs):
  values = {'now': now, 'onroad': True, 'enabled': True, 'wanted': True, 'wifi': False,
            'position': [121., 25.], 'heading': 90., 'fix_time': now, 'speed': 25.}
  values.update(kwargs)
  return values


def test_worker_client_roundtrip_and_expiry(tmp_path):
  client = OsmCurveClient(tmp_path / 'ipc')
  worker = OsmWorker(tmp_path / 'cache', tmp_path / 'ipc')
  worker.store.nearby = lambda _position: [Road(lonlat(road()))]
  assert not client.update(**client_input())[0]
  request = worker.request()
  worker.step(request, 10.)
  points, _ = client.update(**client_input(10.2))
  assert len(points) > 3 and client.status == 'road_matched'
  assert not client.update(**client_input(11.1))[0]
  second = OsmCurveClient(tmp_path / 'ipc')
  assert not second.update(**client_input(10.3))[0]  # old process's reply


@pytest.mark.parametrize('change,status', [({'wanted': False}, 'navigation_priority'),
                                        ({'enabled': False}, 'disabled'),
                                        ({'fix_time': 1.}, 'stale_position')])
def test_worker_clears_unusable_preview(tmp_path, change, status):
  client = OsmCurveClient(tmp_path / 'ipc')
  worker = OsmWorker(tmp_path / 'cache', tmp_path / 'ipc')
  client.update(**client_input(**change))
  worker.step(worker.request(), 10.)
  response = read_message(tmp_path / 'ipc' / 'response.json')
  assert response['status'] == status and not response['points']


@pytest.mark.parametrize('change', [{'onroad': True}, {'wifi': False}, {'enabled': False}, {'stamp': 1.}])
def test_download_requires_fresh_parked_wifi_request(tmp_path, monkeypatch, change):
  worker = OsmWorker(tmp_path / 'cache', tmp_path / 'ipc')
  request = {'session': 'a', 'stamp': 10., 'enabled': True, 'onroad': False, 'wifi': True}
  monkeypatch.setattr('openpilot.selfdrive.carrot.osmd.time.monotonic', lambda: 10.)
  write_message(tmp_path / 'ipc' / 'request.json', request)
  assert worker.download_allowed()
  request.update(change)
  write_message(tmp_path / 'ipc' / 'request.json', request)
  assert not worker.download_allowed()


@pytest.mark.parametrize('bad', [{}, {'stamp': float('nan'), 'session': 'a'}, {'stamp': '10', 'session': 'a'}])
def test_malformed_request_is_not_fresh(bad):
  assert not fresh_request(bad, 10)
  assert not valid_position(bad, 10)


def test_malformed_mailbox_is_ignored(tmp_path):
  path = tmp_path / 'response.json'
  for value in ('broken', '[]', 'x' * 262145):
    path.write_text(value)
    assert read_message(path) == {}


def test_known_four_lane_motorway_accepts_carriageway_not_unbounded_distance():
  motorway = Road(lonlat(road()), True, 4, True)
  matcher = RoadMatcher()
  assert matcher.match([motorway], lonlat((0, 9)), 90)[1] == 'road_matched'
  assert matcher.lateral_allowance == pytest.approx(7.2)
  assert matcher.match([motorway], lonlat((0, 10)), 90)[1] == 'off_road'
  assert matcher.lateral_allowance == 0.
  # A nearby parallel road must not be hidden by the motorway's width.
  parallel = Road(lonlat(road() + [0, 12]), True)
  assert matcher.match([motorway, parallel], lonlat((0, 6)), 90)[1] == 'ambiguous_road'
  assert matcher.lateral_allowance == 0.


@pytest.mark.parametrize('oneway,lanes,motorway', [(False, 4, True), (True, 0, True), (True, 2, True),
                                                (True, 4, False), (True, 8, True)])
def test_unknown_width_links_and_two_way_roads_keep_original_limit(oneway, lanes, motorway):
  matcher = RoadMatcher()
  assert matcher.match([Road(lonlat(road()), oneway, lanes, motorway)], lonlat((0, 9)), 90)[1] == 'off_road'
  assert matcher.lateral_allowance == 0.


def test_corridor_with_unknown_width_does_not_export_lane_allowance():
  first = Road(lonlat(np.array([(0, 0), (100, 0), (200, 0)])), True, 4, True)
  exit_road = Road(lonlat(np.array([(200, 0), (300, 0), (400, 0)])), True)
  matcher = RoadMatcher()
  assert matcher.match([first, exit_road], lonlat((0, 0)), 90)[1] == 'road_matched'
  assert matcher.lateral_allowance == 0.


def test_tile_lane_metadata_survives_decoding(tmp_path):
  archive = make_archive(tmp_path / 'lanes.tar.gz', [Road(lonlat(road()), True, 4, True)])
  install_archive(archive, tmp_path / 'cache', (24, 120))
  roads = TileStore(tmp_path / 'cache').nearby(lonlat((0, 0)))
  assert roads and all(r.lateral_allowance == 7.2 for r in roads)


def test_response_width_is_reset_on_expired_reply(tmp_path):
  client = OsmCurveClient(tmp_path)
  response = {'session': client.session, 'stamp': 10., 'status': 'road_matched',
              'points': lonlat(road()).tolist(), 'id': 'road', 'lateral_allowance': 7.2}
  write_message(tmp_path / 'response.json', response)
  kwargs = dict(onroad=True, enabled=True, wanted=True, wifi=False, position=(121., 25.), heading=90., fix_time=10., speed=25.)
  assert client.update(now=10., **kwargs)[0]
  assert client.lateral_allowance == 7.2
  assert not client.update(now=11.1, **kwargs)[0]
  assert client.lateral_allowance == 0.
  response.update(stamp=11.2, lateral_allowance=100.)
  write_message(tmp_path / 'response.json', response)
  assert not client.update(now=11.4, **kwargs)[0]
  assert client.status == 'invalid_road_width' and client.lateral_allowance == 0.


def test_width_tag_does_not_create_ambiguity_for_distant_candidate():
  main = Road(lonlat(road()), True, 4, True)
  parallel = Road(lonlat(road() + [0, 7]), True)
  matcher = RoadMatcher()
  assert matcher.match([main, parallel], lonlat((0, 0)), 90)[1] == 'road_matched'
  assert matcher.match([main, parallel], lonlat((0, 3.5)), 90)[1] == 'ambiguous_road'


def test_unique_trajectory_can_exclude_disconnected_candidate_but_expires():
  main = Road(lonlat(np.column_stack([np.arange(0, 205, 5), np.zeros(41)])), True)
  alternative = Road(lonlat(np.array([(40., 2.), (80., 2.), (200., 2.)])), True)
  matcher = RoadMatcher()
  for now, x in [(10., 0), (10.2, 12), (10.4, 24)]:
    assert matcher.match([main, alternative], lonlat((x, 0)), 90, now=now, speed=80)[1] == 'road_matched'
  assert matcher.match([main, alternative], lonlat((40, 0)), 90, now=10.6, speed=80)[1] == 'road_tracked'
  # A tracked result never renews the last unique anchor.
  assert matcher.match([main, alternative], lonlat((40, 0)), 90, now=11.01, speed=80)[1] == 'ambiguous_road'


def test_trajectory_cannot_choose_connected_merge_or_reuse_after_jump():
  main = Road(lonlat(np.column_stack([np.arange(0, 205, 5), np.zeros(41)])), True)
  alternative = Road(lonlat(np.array([(40., 2.), (80., 2.), (200., 2.)])), True)
  for jump in (False, True):
    matcher = RoadMatcher()
    for now, x in [(10., 0), (10.2, 12), (10.4, 24)]:
      matcher.match([main, alternative], lonlat((x, 0)), 90, now=now, speed=80)
    roads = [main, alternative]
    if not jump:
      roads.append(Road(lonlat(np.array([(0., 0.), (40., 2.)])), True))
    assert matcher.match(roads, lonlat((40, 0)), 90, now=10.41 if jump else 10.6, speed=80)[1] == 'ambiguous_road'
