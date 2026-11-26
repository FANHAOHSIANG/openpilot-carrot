"""Bound a model-mode curvature trim using the two visible ego-lane markings."""

import math


MIN_SPEED = 30.0 / 3.6
DEADBAND = 0.12  # metres from the lane midpoint
MAX_DISPLACEMENT = 0.20  # metres at any sampled preview point
MAX_ACCEL = 0.15  # m/s² of lateral acceleration correction
ACCEL_STEP = 0.15 * 0.05  # 0.15 m/s³ at the model's 20 Hz rate
CONFIRM_FRAMES = 4


def _sample(line, distances):
  """Linear interpolation on a strictly increasing forward grid, without extrapolation."""
  xs, ys = line.x, line.y
  if len(xs) < 2 or len(xs) != len(ys):
    return None
  x0, y0 = xs[0], ys[0]
  if not (math.isfinite(x0) and math.isfinite(y0)) or x0 > distances[0]:
    return None

  values = []
  for i in range(1, len(xs)):
    x1, y1 = xs[i], ys[i]
    if not (math.isfinite(x1) and math.isfinite(y1)) or x1 <= x0:
      return None
    while distances[len(values)] <= x1:
      x = distances[len(values)]
      values.append(y0 + (y1 - y0) * ((x - x0) / (x1 - x0)))
      if len(values) == len(distances):
        return values
    x0, y0 = x1, y1
  return None


def _target_accel(model, speed):
  raw = model.action.desiredCurvature
  if not (MIN_SPEED <= speed and math.isfinite(speed) and 0.001 <= abs(raw) <= 0.05):
    return 0.0
  if min(len(model.laneLines), len(model.laneLineProbs), len(model.laneLineStds)) < 3:
    return 0.0
  for i in (1, 2):
    if not (0.8 <= model.laneLineProbs[i] <= 1.0 and 0.0 <= model.laneLineStds[i] <= 0.20):
      return 0.0

  preview = min(26.0, max(12.0, 1.2 * speed))
  step = preview / 2.0
  distances = (0.0, step, preview, 3.0 * step)
  left = _sample(model.laneLines[1], distances)
  right = _sample(model.laneLines[2], distances)
  path = _sample(model.position, distances)
  if left is None or right is None or path is None or not (left[0] < 0.0 < right[0]):
    return 0.0

  widths = [r - l for l, r in zip(left, right, strict=True)]
  if not all(2.7 <= width <= 4.5 for width in widths) or max(widths) - min(widths) > 0.65:
    return 0.0
  centers = [(l + r) * 0.5 for l, r in zip(left, right, strict=True)]
  direction = math.copysign(1.0, raw)  # positive y and curvature point right
  # At x=0 the ego reference is y=0. Preserve turn-in if the car is already
  # outside the midpoint and the model is bringing it back toward the lane.
  if direction * (0.0 - centers[0]) < -DEADBAND:
    return 0.0
  slopes = [(centers[i + 1] - centers[i]) / step for i in range(3)]
  if any(abs(slope) > 0.65 for slope in slopes):
    return 0.0
  for first, second in zip(slopes, slopes[1:]):
    # Signed curvature of y(x). Demand agreement at two adjacent locations so
    # the current turn's correction is dropped on approach to an S-curve reversal.
    signed_curve = (second - first) / (step * (1.0 + ((first + second) * 0.5) ** 2) ** 1.5)
    if not (0.0008 <= direction * signed_curve <= 0.05):
      return 0.0

  curvature_limit = 0.2 * abs(raw)
  for i in (1, 2, 3):
    inward = direction * (path[i] - centers[i])
    if not inward > DEADBAND:
      return 0.0
    # Small corrections displace the forward path by ~0.5 * delta_k * x².
    # Bound each checked distance using only its excess inward displacement.
    margin = min(MAX_DISPLACEMENT, inward - DEADBAND)
    curvature_limit = min(curvature_limit, 2.0 * margin / distances[i] ** 2)
  return -direction * min(MAX_ACCEL, curvature_limit * speed ** 2)


class CurveCentering:
  def __init__(self):
    self.reset()

  def reset(self):
    self._direction = 0
    self._frames = 0
    self._accel = 0.0

  def update(self, model, speed: float) -> float:
    """Call once per fresh model frame. Returns an additive curvature in 1/m."""
    try:
      target = _target_accel(model, speed)
    except (AttributeError, IndexError, TypeError, ValueError, OverflowError):
      target = 0.0
    if target == 0.0:
      self.reset()
      return 0.0

    direction = 1 if target > 0.0 else -1
    if direction != self._direction:
      self.reset()
      self._direction = direction
    self._frames = min(self._frames + 1, CONFIRM_FRAMES)
    if self._frames < CONFIRM_FRAMES:
      return 0.0

    # Ramp up only. Always honor a shrinking geometric bound on the current frame.
    self._accel = min(abs(target), self._accel + ACCEL_STEP)
    return direction * self._accel / speed ** 2
