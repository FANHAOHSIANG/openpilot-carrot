"""Bounded YOLO11 ONNX image inference for observation only; no control outputs."""

MODEL_SHA256 = 'f320c020594a3988c118ff076711d45bb6cc45ffea8069fa06743bfc4bcca3de'
LABELS = ('person', 'rider', 'car', 'truck', 'bus', 'train', 'motor', 'bike', 'traffic light', 'traffic sign')
SIDE = 640


def letterbox_rgb(image):
  import numpy as np
  from PIL import Image

  rgb = np.asarray(image)
  if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint8:
    raise ValueError('expected an RGB uint8 image')
  h, w = rgb.shape[:2]
  if min(h, w) <= 0:
    raise ValueError('empty image')
  scale = min(SIDE / w, SIDE / h)
  new_w, new_h = round(w * scale), round(h * scale)
  left, top = (SIDE - new_w) // 2, (SIDE - new_h) // 2
  canvas = Image.new('RGB', (SIDE, SIDE), (114, 114, 114))
  resampling = getattr(Image, 'Resampling', Image)
  canvas.paste(Image.fromarray(rgb).resize((new_w, new_h), resampling.BILINEAR), (left, top))
  tensor = np.asarray(canvas, dtype=np.float32).transpose(2, 0, 1)[None] / 255.0
  return np.ascontiguousarray(tensor), (scale, left, top, w, h)


def _iou(box, boxes):
  import numpy as np

  top_left = np.maximum(box[:2], boxes[:, :2])
  bottom_right = np.minimum(box[2:], boxes[:, 2:])
  wh = np.maximum(0, bottom_right - top_left)
  intersection = wh[:, 0] * wh[:, 1]
  area = np.maximum(0, box[2] - box[0]) * np.maximum(0, box[3] - box[1])
  areas = np.maximum(0, boxes[:, 2] - boxes[:, 0]) * np.maximum(0, boxes[:, 3] - boxes[:, 1])
  return intersection / np.maximum(area + areas - intersection, 1e-9)


def decode_output(output, transform, confidence=0.25, iou_threshold=0.7, limit=30):
  """Decode single-image model output, class-aware NMS; coordinates are image pixels."""
  import numpy as np

  values = np.asarray(output)
  if values.shape != (1, 14, 8400) or not np.isfinite(values).all():
    raise ValueError('unexpected or non-finite model output')
  if not 0 <= confidence <= 1 or not 0 <= iou_threshold <= 1 or not 1 <= limit <= 100:
    raise ValueError('invalid decoder limits')
  if np.any(values[:, 4:, :] < 0) or np.any(values[:, 4:, :] > 1):
    raise ValueError('invalid class confidence')
  scale, left, top, width, height = transform
  if not np.isfinite(scale) or scale <= 0 or width <= 0 or height <= 0:
    raise ValueError('invalid image transform')
  rows = values[0].T
  classes = rows[:, 4:].argmax(axis=1)
  scores = rows[np.arange(len(rows)), 4 + classes]
  keep = (scores >= confidence) & np.isin(classes, (3, 4))
  rows, classes, scores = rows[keep], classes[keep], scores[keep]
  if len(rows) == 0:
    return []
  center, size = rows[:, :2], rows[:, 2:4]
  boxes = np.concatenate((center - size / 2, center + size / 2), axis=1)
  boxes[:, (0, 2)] = np.clip((boxes[:, (0, 2)] - left) / scale, 0, width)
  boxes[:, (1, 3)] = np.clip((boxes[:, (1, 3)] - top) / scale, 0, height)
  good = (boxes[:, 2] > boxes[:, 0]) & (boxes[:, 3] > boxes[:, 1])
  boxes, classes, scores = boxes[good], classes[good], scores[good]
  # Bound work before NMS; preserve deterministic stable score order.
  order = np.argsort(-scores, kind='stable')[:300]
  selected = []
  while len(order) and len(selected) < limit:
    current, rest = int(order[0]), order[1:]
    selected.append(current)
    if len(rest):
      rest = rest[~((classes[rest] == classes[current]) & (_iou(boxes[current], boxes[rest]) > iou_threshold))]
    order = rest
  result = []
  for index in selected:
    box = boxes[index].astype(float).tolist()
    edge = not (2 < box[0] < box[2] < width - 2 and 2 < box[1] < box[3] < height - 2)
    result.append({'label': LABELS[int(classes[index])], 'confidence': float(scores[index]),
                   'box': box, 'edge_clipped': edge})
  return result
