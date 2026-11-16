#!/usr/bin/env python3
"""Replay exported Carrot geometry, optionally with real YOLO video inference.

There is no PubMaster, Params writer, camera warp, planner hook, or control output.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

from openpilot.tools.clearance_shadow.perception import YoloTracker, project_detection
from openpilot.tools.clearance_shadow.policy import Config, OffsetObserver


def sha256(path):
  digest = hashlib.sha256()
  with open(path, 'rb') as source:
    for chunk in iter(lambda: source.read(1024 * 1024), b''):
      digest.update(chunk)
  return digest.hexdigest()


def load_rows(path):
  with open(path) as source:
    for line in source:
      if line.strip():
        yield json.loads(line)


def evaluate(rows, output, observer, tracker=None, video=None, overlay=None):
  """A missing frame/geometry never reuses the previous detection or snapshot."""
  import importlib.metadata
  reasons, classes = Counter(), Counter()
  count, nonzero, frame_index = 0, 0, -1
  infer_times = []
  writer = None
  cap = None
  if video is not None:
    import cv2
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
      raise ValueError(f'cannot decode {video}')
  try:
    with open(output, 'w') as sink:
      last_index = -1
      for row in rows:
        index = int(row['video_index'])
        if index <= last_index:
          raise ValueError('sidecar video_index must be unique and increasing')
        last_index = index
        snapshot = row['snapshot']
        observations, raw, result = [], [], None
        # A provided observations field is explicit replay input, not live detection.
        snapshot = dict(snapshot, perception_valid=False)
        if cap is not None:
          image = None
          while frame_index < index:
            ok, image = cap.read()
            if not ok:
              raise ValueError(f'video ended before sidecar frame {index}')
            frame_index += 1
          if image is None:
            raise ValueError('video/sidecar alignment failure')
          if tracker is not None:
            start = time.monotonic()
            raw, result = tracker.infer(image)
            infer_times.append(time.monotonic() - start)
            camera = snapshot.get('camera', {})
            if camera.get('image_size') == [image.shape[1], image.shape[0]]:
              observations = [project_detection(det, camera) for det in raw]
              snapshot['perception_valid'] = bool(camera.get('valid', False))
        elif 'observations' in row:
          observations = row['observations']
          snapshot['perception_valid'] = bool(row.get('perception_valid', False))
        decision = observer.update(snapshot, observations)
        decision.update(video_index=index, frame_id=row.get('frame_id'), t=snapshot.get('t'),
                        detections=raw, observations=observations)
        sink.write(json.dumps(decision, allow_nan=False) + '\n')
        reasons[decision['reason']] += 1
        classes.update(d['label'] for d in raw)
        count += 1
        nonzero += abs(decision['candidate_offset_m']) > 0.001
        if overlay is not None and result is not None:
          import cv2
          if writer is None:
            writer = cv2.VideoWriter(str(overlay), cv2.VideoWriter_fourcc(*'mp4v'), 20,
                                     (image.shape[1], image.shape[0]))
            if not writer.isOpened():
              raise ValueError('cannot open overlay writer')
          canvas = result.plot()
          text = f'SHADOW ONLY  candidate {decision["candidate_offset_m"] * 100:+.1f} cm  applied 0 cm'
          cv2.putText(canvas, text, (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
          cv2.putText(canvas, decision['reason'], (15, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
          writer.write(canvas)
  finally:
    if cap is not None:
      cap.release()
    if writer is not None:
      writer.release()
  summary = {'frames': count, 'nonzero_candidate_frames': nonzero, 'reasons': dict(reasons),
             'class_observations': dict(classes), 'applied_offset_m': 0, 'control_eligible': False,
             'inference_mean_ms': 1000 * sum(infer_times) / len(infer_times) if infer_times else None,
             'overlay_playback_fps': 20 if overlay else None}
  if tracker is not None:
    summary['ultralytics_version'] = importlib.metadata.version('ultralytics')
  return summary


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--sidecar', type=Path, required=True, help='JSONL from export_rlog')
  parser.add_argument('--mode', choices=['roadside', 'vehicles'], default='vehicles')
  parser.add_argument('--video', type=Path, help='matching, unmodified fcamera.hevc')
  parser.add_argument('--weights', type=Path, help='explicit local YOLO weights; no implicit download')
  parser.add_argument('--device', default='cpu', help='cpu or mps on Mac; no effect without weights')
  parser.add_argument('--offset-cm', type=float, default=15)
  parser.add_argument('--rate-cm-s', type=float, default=5)
  parser.add_argument('--vehicle-width-m', type=float, default=2.0, help='research corridor envelope, verify actual vehicle dimensions')
  parser.add_argument('--output', type=Path, required=True)
  parser.add_argument('--overlay', type=Path, help='annotated review MP4 at fixed 20 fps (not timing evidence)')
  args = parser.parse_args()
  if args.weights and (not args.weights.is_file() or args.video is None):
    parser.error('--weights must exist locally and requires --video')
  if args.overlay and not args.weights:
    parser.error('--overlay requires --weights and --video')
  outputs = [args.output, args.output.with_suffix('.summary.json')] + ([args.overlay] if args.overlay else [])
  inputs = [args.sidecar] + ([args.video] if args.video else []) + ([args.weights] if args.weights else [])
  if len({p.resolve() for p in outputs}) != len(outputs) or any(p.resolve() in {q.resolve() for q in inputs} for p in outputs):
    parser.error('input and output paths must be distinct')
  if any(p.exists() for p in outputs):
    parser.error('output exists; choose new output paths')
  cfg = Config(max_offset_m=args.offset_cm / 100, rate_mps=args.rate_cm_s / 100, vehicle_width_m=args.vehicle_width_m)
  tracker = YoloTracker(args.weights, args.device) if args.weights else None
  summary = evaluate(load_rows(args.sidecar), args.output, OffsetObserver(cfg, args.mode), tracker, args.video, args.overlay)
  summary.update(mode=args.mode, config=vars(cfg), sidecar_sha256=sha256(args.sidecar),
                 weights_sha256=sha256(args.weights) if args.weights else None,
                 video_sha256=sha256(args.video) if args.video else None)
  args.output.with_suffix('.summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
  print(json.dumps(summary, indent=2))


if __name__ == '__main__':
  main()
