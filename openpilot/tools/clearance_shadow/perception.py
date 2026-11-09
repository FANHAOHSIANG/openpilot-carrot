"""YOLO/ByteTrack adapter and approximate ground projection for offline analysis."""
import math

import numpy as np

ROAD_ACTORS = frozenset(('person', 'bicycle', 'car', 'motorcycle', 'bus', 'truck', 'train'))
# The user's BDD model names these classes differently from COCO. Preserve
# riders and two-wheelers as blockers even when the alias is not a truck/bus.
CLASS_ALIASES = {'rider': 'person', 'motor': 'motorcycle', 'bike': 'bicycle'}


def project_detection(det, camera):
  result = dict(det, geometry_valid=False)
  try:
    x1, y1, x2, y2 = map(float, det['box'])
    width, height = camera['image_size']
    if (not camera['valid'] or not all(math.isfinite(v) for v in (x1, y1, x2, y2))
        or not 2 < x1 < x2 < width - 2 or not 2 < y1 < y2 < height - 2):
      return result
    transform = np.asarray(camera['ground_from_image'], dtype=float)
    if transform.shape != (3, 3) or not np.isfinite(transform).all() or np.linalg.cond(transform) > 1e8:
      return result
    points = np.array([[x1, y2, 1.0], [x2, y2, 1.0]]) @ transform.T
    if np.any(np.abs(points[:, 2]) < 1e-8):
      return result
    xy = points[:, :2] / points[:, 2:]
    if not np.isfinite(xy).all() or np.any(xy[:, 0] < 2) or np.any(xy[:, 0] > 45):
      return result
    # Deliberately pessimistic horizontal interval, not a calibrated error distribution.
    uncertainty = 0.30 + 0.01 * float(np.max(xy[:, 0]))
    result.update(geometry_valid=True, x_m=float(np.mean(xy[:, 0])),
                  y_min_m=float(np.min(xy[:, 1]) - uncertainty), y_max_m=float(np.max(xy[:, 1]) + uncertainty))
  except (KeyError, TypeError, ValueError, np.linalg.LinAlgError):
    pass
  return result


def detections_from_result(result):
  """Resolve names from each model's metadata; never assume bus/truck class IDs."""
  detections = []
  if result.boxes is None:
    return detections
  for box in result.boxes:
    raw_label = str(result.names[int(box.cls.item())]).lower().strip()
    label = CLASS_ALIASES.get(raw_label, raw_label)
    if label not in ROAD_ACTORS:
      continue
    track_id = int(box.id.item()) if box.id is not None else None
    detections.append({'label': label, 'raw_label': raw_label, 'track_id': track_id, 'confidence': float(box.conf.item()),
                       'box': [float(v) for v in box.xyxy[0].tolist()]})
  return detections


class YoloTracker:
  def __init__(self, weights, device='cpu', imgsz=640):
    # Kept out of policy/runtime imports. Loading third-party weights is explicit.
    from ultralytics import YOLO
    self.model = YOLO(str(weights))
    self.device, self.imgsz = device, imgsz
    labels = {str(v).lower().strip() for v in self.model.names.values()}
    if not {'bus', 'truck'} <= labels:
      raise ValueError('model metadata must contain bus and truck classes')

  def infer(self, image):
    result = self.model.track(image, persist=True, tracker='bytetrack.yaml', device=self.device,
                              imgsz=self.imgsz, conf=0.25, verbose=False)[0]
    return detections_from_result(result), result
