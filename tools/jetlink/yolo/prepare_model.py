#!/usr/bin/env python3
"""Download hash-pinned official YOLO11n weights and export the display model.

Run in the isolated export environment from README.md, never Jetlink's venv.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

SOURCE = 'https://huggingface.co/Ultralytics/YOLO11/resolve/main/yolo11n.pt'
SOURCE_SHA256 = '0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1'


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('directory', type=Path)
  args = parser.parse_args()
  args.directory.mkdir(parents=True, exist_ok=True)
  weights = args.directory / 'yolo11n.pt'
  if not weights.exists():
    with urllib.request.urlopen(SOURCE, timeout=60) as response:
      content = response.read(8 * 1024 * 1024 + 1)
    if hashlib.sha256(content).hexdigest() != SOURCE_SHA256:
      raise ValueError('Downloaded weights did not match the pinned official checkpoint')
    weights.write_bytes(content)
  if hashlib.sha256(weights.read_bytes()).hexdigest() != SOURCE_SHA256:
    raise ValueError('Existing weights SHA256 mismatch')
  import torch
  from ultralytics import YOLO
  torch.set_num_threads(2)
  exported = Path(YOLO(weights).export(format='onnx', imgsz=[384, 672], batch=1,
                                     opset=17, simplify=False, dynamic=False, device='cpu'))
  manifest = {'source': SOURCE, 'source_sha256': SOURCE_SHA256,
              'onnx_sha256': hashlib.sha256(exported.read_bytes()).hexdigest(),
              'input': [1, 3, 384, 672], 'classes': 'coco',
              'license': 'https://www.ultralytics.com/license'}
  (args.directory / 'manifest.json').write_text(json.dumps(manifest, indent=2))
  print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
  main()
