#!/usr/bin/env python3
"""Opt-in Mac/desktop YOLO worker and offline image/video test runner.

Examples are in yolo/README.md. All output is local display data, never cereal.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from yolo.core import Detector, ground_position
from yolo.transport import Frames, TTL, calibration, read_packet, write_result


def result_for(detector, frame, camera, now=time.monotonic):
  start = now()
  objects = detector.detect(frame['rgb'])
  for obj in objects:
    position = ground_position(obj['box'], camera) if camera else None
    if position:
      obj.update(position)
  end = now()
  valid = 0 <= end - frame['captured_mono'] < TTL
  return {'version': 1, 'mode': 'live', 'status': 'ready' if valid else 'late',
          'written_mono': end, 'captured_mono': frame['captured_mono'],
          'expires_mono': frame['captured_mono'] + TTL, 'frame_id': frame['frame_id'],
          'source_width': frame['source_width'], 'source_height': frame['source_height'],
          'input_resolution': frame['resolution'], 'model_sha256': detector.sha256,
          'inference_ms': round((end-start)*1000, 2), 'calibrated': camera is not None,
          'objects': objects if valid else []}


def run_live(args, detector):
  if Path('/AGNOS').exists():
    raise SystemExit('Run this inference worker on the Mac/desktop host, not on C4')
  try:
    os.nice(10)
  except OSError:
    pass
  import fcntl
  lock = Path(args.output).with_suffix('.lock').open('w')
  try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
  except BlockingIOError:
    raise SystemExit('Another YOLO worker owns this output')
  frames = Frames()
  count, expired, inference = 0, 0, []
  deadline = time.monotonic() + args.seconds if args.seconds else float('inf')
  next_report = 0.
  try:
    while time.monotonic() < deadline:
      start = time.monotonic()
      snapshot = read_packet(args.snapshot, start, time.time() if args.packet_clock == 'epoch' else None)
      frame = frames.take(snapshot, start)
      if frame is None:
        if start >= next_report:
          print(json.dumps({'state': 'waiting_for_fresh_road_frame', 'snapshot': args.snapshot,
                            'snapshot_fresh': snapshot is not None, 'frames': count}), flush=True)
          next_report = start + 5
        time.sleep(.05)
        continue
      result = result_for(detector, frame, calibration(snapshot[1], frame))
      write_result(args.output, result)
      count += 1
      expired += result['status'] != 'ready'
      inference.append(result['inference_ms'])
      inference = inference[-120:]
      if start >= next_report:
        print(json.dumps({'frames': count, 'late': expired, 'input': frame['resolution'],
                          'inference_mean_ms': round(sum(inference)/len(inference), 2),
                          'counts': dict(Counter(o['name'] for o in result['objects'])),
                          'calibrated': result['calibrated']}), flush=True)
        next_report = start + 5
      # No inference queue. At most 2 Hz and 35% of one worker's wall time.
      period = max(1 / args.fps, (time.monotonic()-start) / .35)
      time.sleep(max(0., min(period-(time.monotonic()-start), 2.)))
  finally:
    now = time.monotonic()
    write_result(args.output, {'version': 1, 'mode': 'live', 'status': 'stopped',
                              'written_mono': now, 'captured_mono': now,
                              'expires_mono': now, 'objects': []})
    lock.close()


def run_replay(args, detector):
  import numpy as np
  from PIL import Image, ImageDraw
  source = Path(args.input)
  output = Path(args.output)
  output.mkdir(parents=True, exist_ok=True)
  video = source.suffix.lower() in ('.mp4', '.hevc', '.ts', '.mov', '.mkv')
  capture = None
  if video:
    import cv2
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
      raise ValueError('Could not open video')
  records = []
  try:
    for index in range(args.frames if video else 1):
      if video:
        capture.set(cv2.CAP_PROP_POS_MSEC, index / args.fps * 1000)
        ok, bgr = capture.read()
        if not ok:
          break
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
      else:
        rgb = np.array(Image.open(source).convert('RGB'))
      if args.preview_size:
        rgb = np.array(Image.fromarray(rgb).resize((384, 240), Image.Resampling.BILINEAR))
      start = time.monotonic()
      objects = detector.detect(rgb)
      ms = (time.monotonic()-start)*1000
      records.append({'index': index, 'inference_ms': ms, 'objects': objects})
      image = Image.fromarray(rgb)
      draw = ImageDraw.Draw(image)
      for obj in objects:
        x1, y1, x2, y2 = [v * (image.width if i % 2 == 0 else image.height) for i, v in enumerate(obj['box'])]
        color = {0: '#ff6464', 1: '#ffc84c', 3: '#ffad40'}.get(obj['cls'], '#5ac8ff')
        draw.rectangle((x1, y1, x2, y2), outline=color, width=2)
        draw.text((x1, max(0, y1-13)), f"{obj['name']} {obj['conf']:.0%}", fill=color, stroke_width=1, stroke_fill='black')
      image.save(output / f'frame-{index:04d}.jpg')
  finally:
    if capture is not None:
      capture.release()
  if not records:
    raise ValueError('No decoded video frames')
  report = {'mode': 'offline', 'model_sha256': detector.sha256, 'input': source.name,
            'preview_size': args.preview_size, 'frames': records,
            'counts': dict(Counter(o['name'] for r in records for o in r['objects'])),
            'inference_median_ms': float(np.median([r['inference_ms'] for r in records])),
            'inference_p95_ms': float(np.percentile([r['inference_ms'] for r in records], 95))}
  (output / 'report.json').write_text(json.dumps(report, indent=2))
  print(json.dumps({k: v for k, v in report.items() if k != 'frames'}, indent=2))


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('mode', choices=('live', 'replay'))
  parser.add_argument('--model', required=True)
  parser.add_argument('--sha256', required=True)
  parser.add_argument('--classes', choices=('coco', 'hcop13'), default='coco')
  default_snapshot = (Path(os.environ.get('CARROT_HUD_DIR', str(Path.home()/'Library/Caches/io.zoompilot.jetlink/carrot-hud')))/'snapshot.packet'
                      if sys.platform == 'darwin' else Path('/dev/shm/carrot-jetlink-hud.packet'))
  parser.add_argument('--snapshot', default=str(default_snapshot))
  parser.add_argument('--packet-clock', choices=('epoch', 'monotonic'),
                      default='epoch' if sys.platform == 'darwin' else 'monotonic')
  parser.add_argument('--output', default='/tmp/carrot-hud-yolo.json')
  parser.add_argument('--input')
  parser.add_argument('--frames', type=int, default=60)
  parser.add_argument('--fps', type=float, default=2.)
  parser.add_argument('--seconds', type=float, default=0)
  parser.add_argument('--preview-size', action='store_true', help='Test the existing 384x240 HUD transport resolution')
  args = parser.parse_args()
  if not .2 <= args.fps <= 2 or not 1 <= args.frames <= 10000 or args.seconds < 0:
    parser.error('Use fps 0.2..2, frames 1..10000 and seconds >= 0')
  if args.mode == 'replay' and (not args.input or args.output == '/tmp/carrot-hud-yolo.json'):
    parser.error('Replay needs --input and an --output directory')
  if args.mode == 'live' and Path('/AGNOS').exists():
    parser.error('Run this inference worker on the Mac/desktop host, not on C4')
  detector = Detector(args.model, args.sha256, args.classes)
  try:
    (run_live if args.mode == 'live' else run_replay)(args, detector)
  except KeyboardInterrupt:
    pass


if __name__ == '__main__':
  main()
