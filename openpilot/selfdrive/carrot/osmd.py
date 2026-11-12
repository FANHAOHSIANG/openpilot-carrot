"""Taiwan map cache and destination-free speed-preview worker (CPU only)."""
import math
import os
import time

# This auxiliary process never starts a BLAS thread pool on the model cores.
for thread_setting in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
  os.environ[thread_setting] = '1'

from openpilot.selfdrive.carrot.osm_curve import SHARED_PATH, fresh_request, read_message, valid_position, write_message
from openpilot.selfdrive.carrot.osm_map import (
  CACHE_PATH, GROUPS, REFRESH_SECONDS, DownloadCancelled, RoadMatcher, TileStore, corridor_id, download_group, group_age,
)


class OsmWorker:
  def __init__(self, root=CACHE_PATH, shared=SHARED_PATH):
    self.root, self.shared = root, shared
    self.store = TileStore(root)
    self.matcher = RoadMatcher()
    self.retry_at = {}
    self.ready = 0
    self.next_check = 0.
    self.ages = dict.fromkeys(GROUPS, math.inf)

  def request(self):
    return read_message(self.shared / 'request.json')

  def download_allowed(self):
    request = self.request()
    return (fresh_request(request, time.monotonic()) and request.get('enabled') is True
            and request.get('onroad') is False and request.get('wifi') is True)

  def publish(self, request, status, points=()):
    write_message(self.shared / 'response.json', {
      'session': request.get('session'), 'stamp': request.get('stamp', -1), 'status': status,
      'lateral_allowance': self.matcher.lateral_allowance if points else 0.,
      'ready': self.ready, 'total': len(GROUPS), 'points': points, 'id': corridor_id(points) if len(points) else 'none'})

  def step(self, request, now):
    if not fresh_request(request, now):
      self.publish({}, 'waiting_for_carrot')
      return
    if now >= self.next_check:
      self.ages = {g: group_age(self.root, g) for g in GROUPS}
      self.ready = sum(age < REFRESH_SECONDS for age in self.ages.values())
      self.next_check = now + 60
    if not request.get('enabled'):
      self.publish(request, 'disabled')
      self.matcher = RoadMatcher()
    elif not request.get('onroad'):
      pending = [g for g in GROUPS if self.ages[g] >= REFRESH_SECONDS and now >= self.retry_at.get(g, 0)]
      status = 'maps_ready' if self.ready == len(GROUPS) else ('download_wait' if request.get('wifi') else 'waiting_wifi')
      self.publish(request, status)
      self.matcher = RoadMatcher()
      if pending and self.download_allowed():
        group = pending[0]
        self.publish(request, f'downloading_{group[0]}_{group[1]}')
        try:
          download_group(self.root, group, allowed=self.download_allowed)
          self.next_check = 0.
          self.store = TileStore(self.root)
        except DownloadCancelled:
          self.publish(self.request(), 'download_paused')
        except Exception as error:
          self.retry_at[group] = time.monotonic() + 300
          self.publish(self.request(), f'download_error:{type(error).__name__}')
    elif not request.get('wanted'):
      self.publish(request, 'navigation_priority')
      self.matcher = RoadMatcher()
    elif not valid_position(request, now):
      self.publish(request, 'stale_position')
      self.matcher = RoadMatcher()
    else:
      try:
        roads = self.store.nearby(request['position'])
        points, status = self.matcher.match(roads, request['position'], request['heading'], now=now, speed=request['speed'])
        self.publish(request, status, points)
      except Exception as error:
        reason = str(error) if isinstance(error, ValueError) else type(error).__name__
        self.publish(request, f'map_unavailable:{reason}'[:80])
        self.matcher = RoadMatcher()


def update_interval(cpu_seconds):
  # Leave 600 ms of the client's 1 s validity window for request age,
  # matching and scheduler jitter. This does not renew an old geometry stamp.
  return max(.2, min(.4, cpu_seconds * 5))


def main():
  # Auxiliary work stays off camera/model/control cores and never uses the GPU.
  if hasattr(os, 'sched_setaffinity'):
    os.sched_setscheduler(0, os.SCHED_OTHER, os.sched_param(0))
    allowed = os.sched_getaffinity(0) & {0, 1, 2, 3}
    if allowed:
      os.sched_setaffinity(0, allowed)
    os.nice(15)
  worker = OsmWorker()
  while True:
    started, cpu_started = time.monotonic(), time.process_time()
    try:
      worker.step(worker.request(), started)
    except Exception as error:
      print(f'osmd: {type(error).__name__}', flush=True)
    # At most 5 Hz; target 20% of one CPU for ordinary matching.
    interval = update_interval(time.process_time() - cpu_started)
    time.sleep(max(.01, interval - (time.monotonic() - started)))


if __name__ == '__main__':
  import argparse
  import json
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--status', action='store_true', help='Read cache and worker status without starting a worker')
  parser.add_argument('--cache', type=str, default=str(CACHE_PATH), help='Cache directory for status inspection')
  args = parser.parse_args()
  if args.status:
    status = read_message(SHARED_PATH / 'response.json')
    status.pop('points', None)
    status['groups'] = [{'group': list(g), 'download_age_days': round(age / 86400, 1) if math.isfinite(age) else None}
                        for g in GROUPS for age in [group_age(args.cache, g)]]
    print(json.dumps(status, ensure_ascii=False, indent=2))
  else:
    main()
