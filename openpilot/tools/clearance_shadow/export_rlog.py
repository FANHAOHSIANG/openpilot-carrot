#!/usr/bin/env python3
"""Export a local single-segment rlog as causal geometry for fcamera.hevc replay.

Requires the full openpilot runtime/schema. No vehicle connection or writes.
"""
import argparse
from bisect import bisect_right
import json
from pathlib import Path

import numpy as np

from openpilot.tools.clearance_shadow.run import sha256

SERVICES = ('modelV2', 'carState', 'carControl', 'liveCalibration', 'roadCameraState', 'deviceState')


def latest_before(events, times, t, max_age_ns):
  index = bisect_right(times, t) - 1
  if index < 0 or t - times[index] > max_age_ns or not events[index].valid:
    return None
  return events[index]


def snapshot_at(t_ns, histories, clocks):
  """Only data published before this camera frame is allowed; no look-ahead."""
  found = {}
  for service in SERVICES:
    ttl = 10_000_000_000 if service == 'liveCalibration' else 3_000_000_000 if service == 'deviceState' else 250_000_000
    event = latest_before(histories[service], clocks[service], t_ns, ttl)
    if event is None:
      return {'t': t_ns / 1e9, 'valid': False, 'export_reason': 'missing or stale ' + service}
    found[service] = getattr(event, service)
  md, cs, cc = found['modelV2'], found['carState'], found['carControl']
  snap = {
    't': t_ns / 1e9, 'valid': bool(cs.canValid), 'model_age_s': (t_ns - md.timestampEof) / 1e9,
    'speed_mps': float(cs.vEgo), 'curvature': float(md.action.desiredCurvature),
    'lat_active': bool(cc.latActive), 'steering_pressed': bool(cs.steeringPressed),
    'blinker': bool(cs.leftBlinker or cs.rightBlinker),
    'maneuver': str(md.meta.laneChangeState) != 'off' or str(md.meta.desire) != 'none',
    'lane_lines': [{'x': list(line.x), 'y': list(line.y)} for line in md.laneLines],
    'lane_probs': list(md.laneLineProbs), 'road_edges': [{'x': list(edge.x), 'y': list(edge.y)} for edge in md.roadEdges],
    'edge_stds': list(md.roadEdgeStds), 'path': {'x': list(md.position.x), 'y': list(md.position.y)},
    'camera': {'valid': False},
  }
  calib = found['liveCalibration']
  if str(calib.calStatus) == 'calibrated' and len(calib.rpyCalib) == 3 and len(calib.height) >= 1:
    from openpilot.common.transformations.camera import DEVICE_CAMERAS, get_view_frame_from_calib_frame
    camera = DEVICE_CAMERAS.get((str(found['deviceState'].deviceType), str(found['roadCameraState'].sensor)))
    height = float(calib.height[0])
    if camera is not None and 0.7 <= height <= 2.5:
      fcam = camera.fcam
      projection = fcam.intrinsics @ get_view_frame_from_calib_frame(*calib.rpyCalib, height)
      # Ground z=0 in calibrated x-forward/y-right coordinates.
      ground_from_image = np.linalg.inv(projection[:, [0, 1, 3]])
      snap['camera'] = {'valid': bool(np.isfinite(ground_from_image).all()),
                        'ground_from_image': ground_from_image.tolist(), 'image_size': [fcam.width, fcam.height]}
  return snap


def export_events(events, output):
  histories = {name: [] for name in SERVICES}
  indices = []
  for event in events:
    kind = event.which()
    if kind in histories:
      histories[kind].append(event)
    elif kind == 'roadEncodeIdx' and event.valid:
      indices.append(event.roadEncodeIdx)
  if not indices:
    raise ValueError('no roadEncodeIdx; use full rlog with matching fcamera.hevc, not qcamera')
  segments = {int(idx.segmentNum) for idx in indices}
  if len(segments) != 1:
    raise ValueError('export exactly one video segment at a time')
  clocks = {}
  for name, stream in histories.items():
    stream.sort(key=lambda event: event.logMonoTime)
    clocks[name] = [int(event.logMonoTime) for event in stream]
  indices.sort(key=lambda idx: idx.segmentId)
  if len({idx.segmentId for idx in indices}) != len(indices):
    raise ValueError('duplicate video indices')
  count, invalid = 0, 0
  with open(output, 'w') as sink:
    for idx in indices:
      if not idx.timestampEof:
        raise ValueError('camera EOF timestamp missing')
      snap = snapshot_at(int(idx.timestampEof), histories, clocks)
      row = {'video_index': int(idx.segmentId), 'frame_id': int(idx.frameId), 'snapshot': snap}
      sink.write(json.dumps(row, allow_nan=False) + '\n')
      count += 1
      invalid += not snap['valid']
  return {'frames': count, 'invalid_snapshots': invalid, 'segment': next(iter(segments))}


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('rlog', type=Path)
  parser.add_argument('--output', type=Path, required=True)
  args = parser.parse_args()
  if not args.rlog.is_file() or args.output.exists():
    parser.error('input must be a local rlog and output must not exist')
  from openpilot.tools.lib.logreader import LogReader
  summary = export_events(LogReader(str(args.rlog)), args.output)
  print(json.dumps(dict(summary, rlog_sha256=sha256(args.rlog)), indent=2))


if __name__ == '__main__':
  main()
