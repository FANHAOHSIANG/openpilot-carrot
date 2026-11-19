"""Decode separate HUD model heads in coordinates of their original RGB frame."""
import hashlib
from collections import Counter
from pathlib import Path

import numpy as np

from openpilot.tools.clearance_shadow.onnx_observer import LABELS, SIDE

_PACKAGE = Path(__file__).resolve().parents[3]
_MODELS = {
  'traffic': (Path(__file__).with_name('models') / 'yolo11n-road.onnx',
              '5cc88f7b3208aae79af52f99da1a478a57b6c4a3294044cf39f3ed8352c65c72'),
  'cone': (_PACKAGE / 'selfdrive/carrot/web/vendor/road-detector/cone.onnx',
           '1d5f3cf69883e89ba6e2b3836a0b21623044e9a682f1f00dfbacac97b99baf94'),
}
# A "rider" alone does not identify the type of cycle. Draw the motor/bike
# detection when present and reserve the pedestrian icon for the person class.
_TRAFFIC_LABELS = {
  i: {'motor': 'motorcycle', 'bike': 'bicycle'}.get(label, label)
  for i, label in enumerate(LABELS) if label in ('person', 'car', 'truck', 'bus', 'motor', 'bike')
}
_COCO_LABELS = {0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle', 5: 'bus', 7: 'truck'}
_COCO_WIDTH, _COCO_HEIGHT = 576, 384
_CONE_LABELS = {6: 'cone'}  # cone.onnx has a different class vocabulary.


def _decode(output, shape, labels, left, top, content_w, content_h):
  """Undo the input transform and return current [kind, center-x, bottom-y, w, h, confidence]."""
  output = np.asarray(output)
  if output.shape != shape:
    raise ValueError(f'unexpected HUD detector output shape {output.shape}')
  if not np.isfinite([left, top, content_w, content_h]).all() or min(content_w, content_h) <= 0:
    raise ValueError('invalid HUD detector image transform')
  rows = output[0].T
  probabilities = rows[:, 4:]
  if not np.isfinite(probabilities).all() or np.any(probabilities < 0) or np.any(probabilities > 1):
    raise ValueError('invalid HUD detector class scores')
  if len(labels) == 1:
    # Match the vendor cone decoder: score its named class channel directly.
    cls = next(iter(labels))
    classes = np.full(len(rows), cls)
    scores = probabilities[:, cls]
  else:
    classes = probabilities.argmax(axis=1)
    scores = probabilities[np.arange(len(rows)), classes]
  valid = (scores >= .5) & np.isin(classes, list(labels)) & np.isfinite(rows[:, :4]).all(axis=1)
  valid &= (rows[:, 2] > 1.) & (rows[:, 3] > 1.)
  candidates = np.flatnonzero(valid)
  order = candidates[np.argsort(-scores[candidates], kind='stable')[:300]]

  geometry = rows[order, :4]
  half = geometry[:, 2:] / 2
  corners = np.column_stack((geometry[:, :2] - half, geometry[:, :2] + half))
  corners -= np.array((left, top, left, top), dtype=corners.dtype)
  corners /= np.array((content_w, content_h, content_w, content_h), dtype=corners.dtype)
  np.clip(corners, 0, 1, out=corners)
  widths, heights = (corners[:, 2:] - corners[:, :2]).T
  areas = widths * heights
  remaining = np.flatnonzero((widths > 0) & (heights > 0))
  motor_vehicles = np.isin(classes[order], [i for i, kind in labels.items() if kind in ('car', 'truck', 'bus')])
  result = []
  while len(remaining) and len(result) < 32:
    best, others = remaining[0], remaining[1:]
    x1, _, x2, bottom = corners[best]
    cls = classes[order[best]]
    result.append([labels[int(cls)], float((x1 + x2) / 2), float(bottom), float(widths[best]),
                   float(heights[best]), float(scores[order[best]])])
    # Class-aware suppression keeps e.g. a motorcycle next to a pedestrian.
    intersect_wh = np.maximum(0, np.minimum(corners[best, 2:], corners[others, 2:]) -
                                np.maximum(corners[best, :2], corners[others, :2]))
    intersect = intersect_wh[:, 0] * intersect_wh[:, 1]
    iou = intersect / (areas[best] + areas[others] - intersect)
    duplicate = (classes[order[others]] == cls) & (iou >= .45)
    # A single road vehicle can activate two size/type classes at the same
    # location. Keep separate partially occluded vehicles and nearby riders.
    duplicate |= motor_vehicles[best] & motor_vehicles[others] & (iou >= .80)
    remaining = others[~duplicate]
  return result


def decode_traffic_output(output, transform):
  """Decode an existing truck-best.onnx forward, using letterbox_rgb's transform."""
  scale, left, top, width, height = transform
  return _decode(output, (1, 14, 8400), _TRAFFIC_LABELS, left, top, round(width * scale), round(height * scale))


def decode_cone_output(output):
  """The pinned web cone head uses a stretched 640×640 input with class 6."""
  return _decode(output, (1, 14, 8400), _CONE_LABELS, 0, 0, SIDE, SIDE)


def separate_riders(objects):
  """Represent a clearly paired rider and motorcycle by the motorcycle's ground contact."""
  people = [i for i, row in enumerate(objects) if row[0] == 'person']
  bikes = [i for i, row in enumerate(objects) if row[0] == 'motorcycle']
  pairs = []
  for person in people:
    _, x, foot, w, h, _ = objects[person]
    for bike in bikes:
      _, center, bottom, bw, bh, _ = objects[bike]
      if (abs(x - center) <= .26 * bw and w <= 1.15 * bw and
          bottom - 1.05 * bh <= foot <= bottom - .06 * bh and foot - h < bottom - .8 * bh):
        pairs.append((person, bike))
  # A pedestrian beside a motorcycle, or an ambiguous overlap, stays visible.
  person_hits = Counter(person for person, _ in pairs)
  bike_hits = Counter(bike for _, bike in pairs)
  riders = {person for person, bike in pairs if person_hits[person] == bike_hits[bike] == 1}
  return [row for i, row in enumerate(objects) if i not in riders]


def build_detector(name):
  """Load one net in the HUD worker. The returned callable takes an RGB uint8 image."""
  if name not in _MODELS:
    raise ValueError(f'unknown HUD detector {name!r}')
  import cv2

  path, expected = _MODELS[name]
  with path.open('rb') as source:
    digest = hashlib.file_digest(source, 'sha256').hexdigest()
  if digest != expected:
    raise ValueError(f'{name} HUD model checksum mismatch')
  cv2.setNumThreads(1)
  cv2.ocl.setUseOpenCL(False)
  net = cv2.dnn.readNetFromONNX(str(path))
  net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
  net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

  def detect(rgb):
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3 or min(rgb.shape[:2]) < 2:
      raise ValueError('expected a nonempty HWC RGB uint8 image')
    height, width = rgb.shape[:2]
    if name == 'traffic':
      scale = min(_COCO_WIDTH / width, _COCO_HEIGHT / height)
      new_w, new_h = round(width * scale), round(height * scale)
      if min(new_w, new_h) < 1:
        raise ValueError('unsupported camera aspect ratio')
      left, top = (_COCO_WIDTH - new_w) // 2, (_COCO_HEIGHT - new_h) // 2
      canvas = np.full((_COCO_HEIGHT, _COCO_WIDTH, 3), 114, dtype=np.uint8)
      canvas[top:top + new_h, left:left + new_w] = cv2.resize(rgb, (new_w, new_h))
    else:
      canvas = cv2.resize(rgb, (SIDE, SIDE))  # Stretch, as in the pinned cone manifest.
    net.setInput(cv2.dnn.blobFromImage(canvas, scalefactor=1 / 255., swapRB=False))
    output = net.forward('output0')
    if name == 'traffic':
      return separate_riders(_decode(output, (1, 84, 4536), _COCO_LABELS, left, top, new_w, new_h))
    return decode_cone_output(output)

  return detect
