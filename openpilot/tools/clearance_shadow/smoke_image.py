#!/usr/bin/env python3
"""Reproducible real-model smoke test; repeated still images are NOT driving validation."""
import argparse
import importlib.metadata
import json
from pathlib import Path

from openpilot.tools.clearance_shadow.perception import YoloTracker
from openpilot.tools.clearance_shadow.run import sha256


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--weights', type=Path, required=True)
  parser.add_argument('--image', type=Path, required=True)
  parser.add_argument('--expect', choices=['bus', 'truck'], default='bus')
  parser.add_argument('--device', default='cpu')
  parser.add_argument('--output', type=Path, required=True)
  args = parser.parse_args()
  if not args.weights.is_file() or not args.image.is_file() or args.output.exists():
    parser.error('inputs must exist locally; output must be new')
  import cv2
  image = cv2.imread(str(args.image))
  if image is None:
    parser.error('cannot decode image')
  tracker = YoloTracker(args.weights, args.device)
  frames = [tracker.infer(image)[0] for _ in range(3)]
  ids = [{d['track_id'] for d in frame if d['label'] == args.expect and d['track_id'] is not None} for frame in frames]
  report = {'scope': 'repeated public still-image inference; not driving/accuracy/clearance validation',
            'model_sha256': sha256(args.weights), 'image_sha256': sha256(args.image),
            'ultralytics_version': importlib.metadata.version('ultralytics'),
            'expected_class': args.expect, 'stable_id_detected': bool(set.intersection(*ids)), 'frames': frames}
  args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
  print(json.dumps({k: v for k, v in report.items() if k != 'frames'}, indent=2))
  if not report['stable_id_detected']:
    raise SystemExit(1)


if __name__ == '__main__':
  main()
