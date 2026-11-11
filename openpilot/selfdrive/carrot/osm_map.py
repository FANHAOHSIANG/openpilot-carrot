"""Resident Taiwan OSM road geometry. No routing, steering or speed commands.

Mapd packed tiles are data only. Downloads and decoding belong in osmd, never
the 20 Hz CarrotMan thread. No GPS coordinates are sent to the map server.
"""
from collections import OrderedDict, defaultdict
from contextlib import closing
from dataclasses import dataclass
import gzip
import hashlib
import math
from pathlib import Path
import re
import sqlite3
import tarfile
import time
import urllib.request

import numpy as np

from openpilot.selfdrive.carrot.route_curve import METRES_PER_DEGREE

MAP_URL = 'https://map-data.pfeifer.dev/offline'
CACHE_PATH = Path('/data/media/0/carrot_osm')
# Whole main island, Penghu, Kinmen (including Wuqiu), and Matsu. These are
# coverage rectangles, not political/administrative boundary definitions.
TAIWAN_BOUNDS = ((21.75, 119.75, 25.5, 122.0), (23.0, 119.25, 24.0, 120.0),
                 (24.25, 118.0, 24.75, 118.75), (24.75, 119.25, 25.25, 119.75),
                 (25.75, 119.75, 26.5, 120.75))
GROUPS = ((24, 120), (22, 120), (20, 120), (22, 118), (24, 118), (26, 118),
          (26, 120), (20, 118))
MAX_ARCHIVE = 256 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
MAX_TILE = 16 * 1024 * 1024
REFRESH_SECONDS = 30 * 86400
EXPIRE_SECONDS = 90 * 86400
_SCHEMA = None


def schema():
  global _SCHEMA
  if _SCHEMA is None:
    import capnp
    _SCHEMA = capnp.load(str(Path(__file__).with_name('osm_offline.capnp')))
  return _SCHEMA


def covered(lat, lon):
  return any(a <= lat <= c and b <= lon <= d for a, b, c, d in TAIWAN_BOUNDS)


def tile_bounds(lat, lon):
  a, b = math.floor(lat * 4) / 4, math.floor(lon * 4) / 4
  return a, b, a + .25, b + .25


def tile_name(bounds):
  return '_'.join(f'{v:.6f}' for v in bounds)


def wanted_tile(bounds):
  a, b, c, d = bounds
  return any(a < y2 and c > y1 and b < x2 and d > x1 for y1, x1, y2, x2 in TAIWAN_BOUNDS)


def group_path(root, group):
  return Path(root) / f'{group[0]}_{group[1]}.sqlite'


def checked_tile(data, bounds):
  if not 0 < len(data) <= MAX_TILE:
    raise ValueError('tile_size')
  reader = schema().Offline.from_bytes_packed(data, traversal_limit_in_words=16 * 1024 * 1024)
  actual = (reader.minLat, reader.minLon, reader.maxLat, reader.maxLon)
  if not np.allclose(actual, bounds, rtol=0, atol=1e-7) or len(reader.ways) > 200000:
    raise ValueError('tile_bounds_or_size')
  return reader


class DownloadCancelled(Exception):
  pass


def install_archive(archive, root, group, fetched_at=None, allowed=lambda: True):
  """Validate all entries and gzip CRC before atomically replacing a group DB."""
  root = Path(root)
  root.mkdir(parents=True, exist_ok=True)
  destination = group_path(root, group)
  staging = destination.with_suffix('.part')
  staging.unlink(missing_ok=True)
  seen, retained, total = set(), 0, 0
  prefix = f'offline/{group[0]}/{group[1]}/'
  conn = sqlite3.connect(staging)
  try:
    conn.execute('CREATE TABLE tiles (name TEXT PRIMARY KEY, data BLOB NOT NULL)')
    conn.execute('CREATE TABLE metadata (fetched_at REAL NOT NULL, format INTEGER NOT NULL)')
    with gzip.open(archive, 'rb') as stream:
      with tarfile.open(fileobj=stream, mode='r|') as tar:
        for member in tar:
          if not allowed():
            raise DownloadCancelled()
          total += member.size
          if total > MAX_EXPANDED:
            raise ValueError('archive_too_large')
          if member.isdir():
            continue
          if not member.isfile() or not member.name.startswith(prefix) or member.size > MAX_TILE:
            raise ValueError('invalid_archive_entry')
          name = member.name[len(prefix):]
          if not re.fullmatch(r'-?\d+\.\d{6}(?:_-?\d+\.\d{6}){3}', name) or name in seen:
            raise ValueError('invalid_tile_name')
          bounds = tuple(map(float, name.split('_')))
          a, b, c, d = bounds
          if (bounds != tile_bounds(a, b) or not group[0] <= a < group[0] + 2
              or not group[1] <= b < group[1] + 2):
            raise ValueError('unexpected_tile_bounds')
          seen.add(name)
          data = tar.extractfile(member).read(MAX_TILE + 1)
          checked_tile(data, bounds)
          if wanted_tile(bounds):
            conn.execute('INSERT INTO tiles VALUES (?, ?)', (name, data))
            retained += 1
      # Tar EOF precedes the gzip trailer. Drain to verify CRC/truncation too.
      while chunk := stream.read(65536):
        total += len(chunk)
        if total > MAX_EXPANDED:
          raise ValueError('archive_padding_too_large')
    # Upstream archives contain all 8 x 8 quarter-degree tiles, including sea.
    expected = {tile_name((group[0] + i / 4, group[1] + j / 4, group[0] + (i + 1) / 4, group[1] + (j + 1) / 4))
                for i in range(8) for j in range(8)}
    if seen != expected or not retained:
      raise ValueError('incomplete_archive')
    # Persistent cache age must survive reboot; monotonic is only used for IPC.
    conn.execute('INSERT INTO metadata VALUES (?, 1)', (time.time() if fetched_at is None else fetched_at,))  # noqa: TID251
    conn.commit()
    conn.close()
    if not allowed():
      raise DownloadCancelled()
    with staging.open('rb') as file:
      import os
      os.fsync(file.fileno())
    staging.replace(destination)
  finally:
    conn.close()
    staging.unlink(missing_ok=True)
  return retained


def download_group(root, group, allowed=lambda: True):
  root = Path(root)
  root.mkdir(parents=True, exist_ok=True)
  temporary = root / 'download.part'
  try:
    if not allowed():
      raise DownloadCancelled()
    request = urllib.request.Request(f'{MAP_URL}/{group[0]}/{group[1]}.tar.gz', headers={'User-Agent': 'Carrot-OSM-Curve/1'})
    with urllib.request.urlopen(request, timeout=10) as response, temporary.open('wb') as output:
      declared = int(response.headers.get('Content-Length', -1))
      if response.status != 200 or declared > MAX_ARCHIVE:
        raise ValueError('download_size_or_status')
      written = 0
      while chunk := response.read(65536):
        if not allowed():
          raise DownloadCancelled()
        written += len(chunk)
        if written > MAX_ARCHIVE:
          raise ValueError('download_too_large')
        output.write(chunk)
      if declared >= 0 and written != declared:
        raise ValueError('truncated_download')
    return install_archive(temporary, root, group, allowed=allowed)
  finally:
    temporary.unlink(missing_ok=True)


def group_age(root, group, now=None):
  path = group_path(root, group)
  try:
    with closing(sqlite3.connect(f'file:{path}?mode=ro', uri=True)) as conn:
      stamp, version = conn.execute('SELECT fetched_at, format FROM metadata').fetchone()
    age = (time.time() if now is None else now) - stamp  # noqa: TID251
    return age if version == 1 and math.isfinite(age) and age >= 0 else math.inf
  except (OSError, sqlite3.Error, TypeError, ValueError):
    return math.inf


@dataclass(frozen=True)
class Road:
  points: np.ndarray
  oneway: bool = False


class TileStore:
  def __init__(self, root=CACHE_PATH):
    self.root = Path(root)
    self.cache = OrderedDict()

  def _load(self, bounds):
    lat, lon = bounds[:2]
    group = (math.floor(lat / 2) * 2, math.floor(lon / 2) * 2)
    if group_age(self.root, group) >= EXPIRE_SECONDS:
      raise ValueError('maps_missing_or_old')
    path = group_path(self.root, group)
    key = (bounds, path.stat().st_mtime_ns)
    if key not in self.cache:
      with closing(sqlite3.connect(f'file:{path}?mode=ro', uri=True)) as conn:
        row = conn.execute('SELECT data FROM tiles WHERE name=?', (tile_name(bounds),)).fetchone()
      if row is None:
        raise ValueError('tile_missing')
      reader = checked_tile(row[0], bounds)
      roads, boxes, nodes = [], [], 0
      for way in reader.ways:
        nodes += len(way.nodes)
        if nodes > 2000000:
          raise ValueError('tile_nodes')
        if len(way.nodes) > 20000:
          raise ValueError('oversized_way')
        if len(way.nodes) < 2:
          continue
        points = np.array([(n.longitude, n.latitude) for n in way.nodes])
        if not np.isfinite(points).all() or np.any(np.abs(points) > [180, 85]):
          raise ValueError('invalid_way')
        roads.append(Road(points, bool(way.oneWay)))
        boxes.append([*points.min(axis=0), *points.max(axis=0)])
      self.cache[key] = (tuple(roads), np.asarray(boxes).reshape(-1, 4))
      while len(self.cache) > 4:
        self.cache.popitem(last=False)
    self.cache.move_to_end(key)
    return self.cache[key]

  def nearby(self, position):
    lon, lat = position
    if not covered(lat, lon):
      raise ValueError('outside_coverage')
    scale = np.array([METRES_PER_DEGREE * math.cos(math.radians(lat)), METRES_PER_DEGREE])
    margin = 750 / scale
    minimum, maximum = np.array(position) - margin, np.array(position) + margin
    result = []
    # Load every tile touching the preview, including adjacent archive groups.
    # Missing neighbors invalidate the corridor instead of hiding a junction.
    for y in range(math.floor(minimum[1] * 4), math.floor(maximum[1] * 4) + 1):
      for x in range(math.floor(minimum[0] * 4), math.floor(maximum[0] * 4) + 1):
        roads, boxes = self._load((y / 4, x / 4, (y + 1) / 4, (x + 1) / 4))
        selected = np.flatnonzero(np.all(boxes[:, :2] <= maximum, axis=1) & np.all(boxes[:, 2:] >= minimum, axis=1))
        result.extend(roads[i] for i in selected)
    return result


class RoadMatcher:
  """Unique directed corridor, truncated at every ambiguous junction.

  Mapd does not retain node IDs, layers or turn restrictions. Coordinate
  equality is used only to connect geometry. Multiple continuations always
  end the preview, even if a name, road class or heading looks preferable.
  """
  def __init__(self):
    self.previous = ()

  def match(self, roads, position, heading):
    scale = np.array([METRES_PER_DEGREE * math.cos(math.radians(position[1])), METRES_PER_DEGREE])
    outgoing, incoming = defaultdict(set), defaultdict(set)
    nodes, indices = [], {}

    def node(point):
      key = tuple(np.round(point, 7))
      if key not in indices:
        indices[key] = len(nodes)
        nodes.append(key)
      return indices[key]

    for road in roads:
      points = (road.points - position) * scale
      # Exclude remote segments of long ways, retaining an ample junction margin.
      valid = np.flatnonzero(np.all(np.minimum(points[:-1], points[1:]) <= 750, axis=1)
                             & np.all(np.maximum(points[:-1], points[1:]) >= -750, axis=1))
      for i in valid:
        a, b = node(road.points[i]), node(road.points[i + 1])
        if a == b:
          continue
        outgoing[a].add(b)
        incoming[b].add(a)
        if not road.oneway:
          outgoing[b].add(a)
          incoming[a].add(b)
    if not nodes:
      return (), 'no_roads'
    coords = np.asarray(nodes)
    xy = (coords - position) * scale
    edges = np.asarray([(a, b) for a, targets in outgoing.items() for b in targets], dtype=int)
    if not len(edges):
      return (), 'no_roads'
    a, b = xy[edges[:, 0]], xy[edges[:, 1]]
    delta = b - a
    lengths = np.linalg.norm(delta, axis=1)
    t = np.clip(np.sum(-a * delta, axis=1) / np.maximum(lengths**2, 1e-9), 0, 1)
    error = np.linalg.norm(a + t[:, None] * delta, axis=1)
    angle = math.radians(heading)
    alignment = delta @ [math.sin(angle), math.cos(angle)] / np.maximum(lengths, 1e-9)
    candidates = np.flatnonzero((error <= 8) & (alignment >= math.cos(math.radians(30))))
    if not len(candidates):
      return (), 'off_road'
    best = candidates[np.argmin(error[candidates])]
    first, last = map(int, edges[best])
    path, seen = [first, last], {first, last}

    def extend(reverse):
      distance = 0.
      while len(path) < 4096 and distance < 650:
        previous, current = (path[1], path[0]) if reverse else (path[-2], path[-1])
        options = (incoming if reverse else outgoing)[current] - {previous}
        if len(options) != 1:
          break
        nxt = next(iter(options))
        # Do not extend across a merge when tracing backwards: the start
        # point must not imply which approach the driver used.
        if nxt in seen:
          break
        seen.add(nxt)
        distance += float(np.linalg.norm(xy[nxt] - xy[current]))
        if reverse:
          path.insert(0, nxt)
        else:
          path.append(nxt)

    extend(False)
    extend(True)
    route_edges = set(zip(path[:-1], path[1:], strict=True))
    for candidate in candidates:
      if error[candidate] <= error[best] + 3 and tuple(edges[candidate]) not in route_edges:
        return (), 'ambiguous_road'
    if len(path) < 3:
      return (), 'short_road'
    points = tuple(map(tuple, coords[path]))
    best_edge = (tuple(coords[first]), tuple(coords[last]))
    old_edges = list(zip(self.previous[:-1], self.previous[1:], strict=True))
    new_edges = set(zip(points[:-1], points[1:], strict=True))
    if best_edge in old_edges:
      old_forward = old_edges[old_edges.index(best_edge):]
      remaining = sum(float(np.linalg.norm((np.array(b) - a) * scale)) for a, b in old_forward)
      # Keep a stationary route ID while driving; otherwise every 5 m map
      # vertex would restart the multi-frame visual confirmation timer.
      if (remaining > 550 or self.previous[-1] == points[-1]) and all(edge in new_edges for edge in old_forward):
        return self.previous, 'road_matched'
    self.previous = points
    return points, 'road_matched'


def corridor_id(points):
  return hashlib.sha256(np.asarray(points, dtype='<f8').tobytes()).hexdigest()[:20]
