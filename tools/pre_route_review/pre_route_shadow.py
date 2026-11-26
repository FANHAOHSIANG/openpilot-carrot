"""Offline PRE route lifecycle diagnostics. No speed or actuator output.

Inputs are a proposed normalized contract, not verified Amap fields. Never
substitute timestamps, road names or nearby exits for stable provider IDs.
"""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Observation:
  session: str
  selected_route: str
  event_route: str
  event_id: str
  kind: str
  guidance_active: bool
  off_route: bool
  position_matched: bool
  completed: bool
  progress_m: float
  entry_m: float
  end_m: float
  distance_to_entry_m: float
  age_ms: float


class PreRouteShadow:
  """Return a diagnostic reason, not permission to command a speed."""
  def __init__(self):
    self.session = None
    self.retired = set()
    self.last_progress = {}

  def observe(self, o: Observation) -> str:
    if not all(type(v) is str and v for v in (o.session, o.selected_route, o.event_route, o.event_id)):
      return 'missing_identity'
    if self.session is None:
      self.session = o.session
    # A new verified navigation session requires a new shadow instance;
    # old packets cannot silently reset its memory.
    if o.session != self.session:
      return 'session_changed'
    if o.selected_route != o.event_route:
      return 'not_selected_route'
    key = (o.event_route, o.event_id)
    if key in self.retired:
      return 'retired'
    if o.kind not in ('exit', 'interchange', 'merge'):
      return 'not_ramp'
    if not o.guidance_active or o.off_route:
      return 'no_guidance'
    values = (o.progress_m, o.entry_m, o.end_m, o.distance_to_entry_m, o.age_ms)
    if not all(type(v) in (int, float) and isfinite(v) for v in values):
      return 'invalid_geometry'
    if not 0 <= o.age_ms < 2000 or not o.position_matched:
      return 'unverified_position'
    if not 0 <= o.entry_m < o.end_m or o.progress_m < 0:
      return 'invalid_geometry'
    if o.completed or o.progress_m >= o.end_m:
      self.retired.add(key)
      return 'completed'
    if abs((o.entry_m - o.progress_m) - o.distance_to_entry_m) > 10:
      return 'inconsistent_distance'
    previous = self.last_progress.get(key)
    if previous is not None and o.progress_m < previous - 10:
      return 'regressed_progress'
    self.last_progress[key] = max(o.progress_m, previous if previous is not None else o.progress_m)
    return 'approach' if o.progress_m < o.entry_m else 'on_ramp'
