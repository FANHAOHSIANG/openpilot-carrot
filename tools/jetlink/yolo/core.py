"""YOLO11 ONNX adapter, based on Henry's hcop yolo_core (see NOTICE).

Inference stays in a separate host process. Boxes are normalized to the FULL input
image, not the letterbox. Only six road-user classes leave this module.
"""
import ast
import hashlib
import math
from pathlib import Path

import numpy as np
from PIL import Image

CLASSES = {0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle', 5: 'bus', 7: 'truck'}
HCOP_CLASSES = ['person', 'bicycle', 'car', 'motorcycle', 'bus', 'truck', 'stop_sign',
                'light_red', 'light_green', 'light_yellow', 'light_off', 'light_pedestrian', 'light_green_arrow']
HCOP_TO_COCO = {0: 0, 1: 1, 2: 2, 3: 3, 4: 5, 5: 7}
MAX_OBJECTS = 32


def letterbox(rgb, width, height):
  h, w = rgb.shape[:2]
  ratio = min(width / w, height / h)
  rw, rh = round(w * ratio), round(h * ratio)
  left, top = (width - rw) // 2, (height - rh) // 2
  padded = np.full((height, width, 3), 114, np.uint8)
  padded[top:top + rh, left:left + rw] = Image.fromarray(rgb).resize((rw, rh), Image.Resampling.BILINEAR)
  return np.ascontiguousarray(padded.transpose(2, 0, 1)[None], dtype=np.float32) / 255, (rw / w, rh / h, left, top)


def nms(boxes, scores, threshold=.45):
  order = scores.argsort()[::-1][:300]
  areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
  keep = []
  while order.size and len(keep) < MAX_OBJECTS:
    i, rest = order[0], order[1:]
    keep.append(i)
    intersect = np.maximum(0, np.minimum(boxes[i, 2:], boxes[rest, 2:]) -
                           np.maximum(boxes[i, :2], boxes[rest, :2])).prod(axis=1)
    iou = intersect / (areas[i] + areas[rest] - intersect + 1e-9)
    order = rest[iou <= threshold]
  return keep


def is_rider(person, machine):
  px1, _, px2, py2 = person
  mx1, my1, mx2, my2 = machine
  mw, mh = mx2 - mx1, my2 - my1
  return (mw > 0 and mh > 0 and abs((px1 + px2 - mx1 - mx2) / 2) <= mw * .7
          and my1 - mh * .6 < py2 < my2 + mh * .3)


def decode(output, transform, image_size, class_map, threshold=.35):
  if output.ndim != 3 or output.shape[0] != 1 or output.shape[1] not in (84, 17) or output.shape[2] > 40000:
    raise ValueError('Expected YOLO11 detect output [1,84,N] or HCOP [1,17,N], without embedded NMS')
  p = output[0].T
  cls = np.argmax(p[:, 4:], axis=1)
  conf = p[np.arange(len(p)), cls + 4]
  valid = np.isfinite(p).all(axis=1) & (conf >= threshold) & (conf <= 1) & np.isin(cls, list(class_map))
  p, cls, conf = p[valid], cls[valid], conf[valid]
  sx, sy, left, top = transform
  w, h = image_size
  boxes = np.column_stack(((p[:, 0] - p[:, 2] / 2 - left) / sx / w,
                           (p[:, 1] - p[:, 3] / 2 - top) / sy / h,
                           (p[:, 0] + p[:, 2] / 2 - left) / sx / w,
                           (p[:, 1] + p[:, 3] / 2 - top) / sy / h))
  boxes = np.clip(boxes, 0, 1)
  valid = (boxes[:, 2] > boxes[:, 0]) & (boxes[:, 3] > boxes[:, 1])
  boxes, cls, conf = boxes[valid], cls[valid], conf[valid]
  dets = []
  for c in np.unique(cls):
    idx = np.where(cls == c)[0]
    for k in nms(boxes[idx], conf[idx]):
      i, label = idx[k], class_map[int(c)]
      dets.append({'cls': label, 'name': CLASSES[label], 'conf': round(float(conf[i]), 4),
                   'box': [round(float(v), 6) for v in boxes[i]]})
  machines = [d['box'] for d in dets if d['cls'] in (1, 3)]
  dets = [d for d in dets if d['cls'] != 0 or not any(is_rider(d['box'], b) for b in machines)]
  return sorted(dets, key=lambda d: -d['conf'])[:MAX_OBJECTS]


class Detector:
  def __init__(self, model, sha256, classes='coco', threads=2):
    import onnxruntime as ort
    if hashlib.sha256(Path(model).read_bytes()).hexdigest() != sha256.lower():
      raise ValueError('Model SHA256 mismatch')
    options = ort.SessionOptions()
    options.intra_op_num_threads, options.inter_op_num_threads = threads, 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    self.session = ort.InferenceSession(str(model), options, providers=['CPUExecutionProvider'])
    inputs, outputs = self.session.get_inputs(), self.session.get_outputs()
    if len(inputs) != 1 or len(outputs) != 1:
      raise ValueError('Only single-input, single-output detection models are supported')
    shape = inputs[0].shape
    if (len(shape) != 4 or shape[:2] != [1, 3] or inputs[0].type != 'tensor(float)' or
        not all(type(v) is int and 32 <= v <= 1024 and v % 32 == 0 for v in shape[2:])):
      raise ValueError('Export a fixed-shape float32 RGB model, batch=1, up to 1024 pixels')
    metadata = self.session.get_modelmeta().custom_metadata_map
    names = ast.literal_eval(metadata.get('names', '{}'))
    if isinstance(names, list):
      names = dict(enumerate(names))
    expected = CLASSES if classes == 'coco' else dict(enumerate(HCOP_CLASSES))
    count = 80 if classes == 'coco' else 13
    if not isinstance(names, dict) or len(names) != count or any(names.get(k) != v for k, v in expected.items()):
      raise ValueError('Model class metadata does not match the selected class order')
    if metadata.get('task') != 'detect':
      raise ValueError('Expected a detection model')
    self.height, self.width = shape[2:]
    self.input_name = inputs[0].name
    self.class_map = {c: c for c in CLASSES} if classes == 'coco' else HCOP_TO_COCO
    self.channels = count + 4
    self.sha256 = sha256.lower()

  def detect(self, rgb, threshold=.35):
    x, transform = letterbox(rgb, self.width, self.height)
    output = self.session.run(None, {self.input_name: x})[0]
    if output.ndim != 3 or output.shape[1] != self.channels:
      raise ValueError('Model output and class metadata disagree')
    return decode(output, transform, (rgb.shape[1], rgb.shape[0]), self.class_map, threshold)


def ground_position(box, camera):
  """Intersect box bottom with calibrated ground; metres, lateral positive right.

  No guessed height, no Custin-specific 0.9 multiplier, no radar association.
  Retain the 2-D class when calibration or ground intersection is unavailable.
  """
  try:
    w, h, f = (camera[k] for k in ('width', 'height', 'focal'))
    roll, pitch, yaw = camera['rpy']
    height = camera['height_m']
    values = [w, h, f, roll, pitch, yaw, height, *box]
    if not all(math.isfinite(v) for v in values) or not .5 <= height <= 3 or min(w, h, f) <= 0:
      return None
    if max(abs(roll), abs(pitch), abs(yaw)) > .25 or box[3] >= .985:
      return None
    cr, sr, cp, sp, cy, sy = math.cos(roll), math.sin(roll), math.cos(pitch), math.sin(pitch), math.cos(yaw), math.sin(yaw)
    rotation = np.array([[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
                         [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr], [-sp, cp*sr, cp*cr]])
    view_from_road = np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0]]) @ rotation @ np.diag([1, -1, -1])
    ray = np.array([((box[0]+box[2])/2*w - w/2)/f, (box[3]*h-h/2)/f, 1.])
    direction = view_from_road.T @ ray
    origin = view_from_road.T @ np.array([0., -height, 0.])
    if abs(direction[2]) < 1e-5:
      return None
    distance = -origin[2] / direction[2]
    road = origin + distance * direction
    if distance <= 0 or not 2 <= road[0] <= 80 or abs(road[1]) > 20:
      return None
    return {'d': round(float(road[0]), 1), 'lat': round(float(-road[1]), 2), 'range_source': 'monocular_estimate'}
  except (KeyError, TypeError, ValueError):
    return None
