"""Offline braking-distance feasibility, not a longitudinal controller.

Inputs must be explicit conservative road-curvature bounds at forward distances.
Model action curvature is not independent road truth. No default vehicle
capability is supplied. Jerk, road friction, banking and traffic are not modeled.
"""
from dataclasses import dataclass
import math

from openpilot.tools.curve_centering.centering_shadow import finite


@dataclass(frozen=True)
class CurvatureConstraint:
  distance_m: float
  abs_curvature_upper: float


def preview_speed_limit(constraints, *, requested_speed, lateral_budget, decel, latency):
  """Return a hypothetical present speed bound and limiting point.

  For each future cap vc, solve v*latency + (v²-vc²)/(2*decel) <= distance.
  A speed already <= vc requires no braking, so the solution never lowers that
  individual constraint below vc. Applies latency once per constraint, not once
  per discretization step. Input is a fully supplied finite preview; unseen
  geometry beyond it is unknown, not assumed straight.
  """
  if (not all(finite(x) for x in (requested_speed, lateral_budget, decel, latency))
      or requested_speed <= 0 or lateral_budget <= 0 or decel <= 0 or latency < 0):
    raise ValueError('invalid feasibility assumptions')
  points = list(constraints)
  if not points:
    raise ValueError('missing road preview')
  previous = -1.0
  best, limiting = requested_speed, None
  for point in points:
    if (not isinstance(point, CurvatureConstraint) or not finite(point.distance_m)
        or not finite(point.abs_curvature_upper) or point.distance_m < 0
        or point.distance_m <= previous or point.abs_curvature_upper < 0):
      raise ValueError('invalid or unordered road preview')
    previous = point.distance_m
    if point.abs_curvature_upper == 0:
      continue
    curve_cap = math.sqrt(lateral_budget/point.abs_curvature_upper)
    reaction = decel*latency
    allowed = max(curve_cap, math.sqrt(reaction**2 + curve_cap**2 + 2*decel*point.distance_m)-reaction)
    if allowed < best:
      best, limiting = allowed, point.distance_m
  return {'speed_mps':best, 'limiting_distance_m':limiting,
          'preview_end_m':points[-1].distance_m,
          'scope':'offline_assumed_road_and_capability_not_vehicle_command'}
