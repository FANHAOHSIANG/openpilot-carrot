"""Offline diagnostics only; no speed, steering or lamp outputs.
All route context fields require a verified provider mapping before use.
"""
from dataclasses import dataclass
from math import isfinite

@dataclass(frozen=True)
class RouteContext:
  session: str
  route: str
  revision: int
  active: bool

@dataclass(frozen=True)
class Event:
  session: str
  route: str
  revision: int
  event_id: str
  sequence: int
  kind: str
  progress: float
  entry: float
  end: float
  distance: float
  age_ms: float
  matched: bool
  completed: bool = False

class RouteAudit:
  def __init__(self):
    self.context = None
    self.events = {}

  def observe(self, context, event):
    if not context.active:
      return 'no_guidance'
    if not context.session or not context.route or type(context.revision) is not int or context.revision < 0:
      return 'invalid_context'
    # Context must be provided independently by an authoritative route source.
    if self.context is not None and context.session == self.context.session:
      if context.revision < self.context.revision or (context.revision == self.context.revision and context.route != self.context.route):
        return 'old_context'
    if self.context != context:
      self.context = context
      self.events.clear()
    if (event.session, event.route, event.revision) != (context.session, context.route, context.revision):
      return 'not_current_route'
    if not event.event_id or type(event.sequence) is not int or event.sequence < 0:
      return 'invalid_identity'
    if event.kind not in ('exit', 'merge', 'interchange'):
      return 'not_ramp'
    values = (event.progress, event.entry, event.end, event.distance, event.age_ms)
    if not all(type(v) in (int, float) and isfinite(v) for v in values):
      return 'invalid_geometry'
    if not event.matched or not 0 <= event.age_ms < 2000:
      return 'unverified_position'
    if not 0 <= event.entry < event.end or event.progress < 0 or abs(event.entry - event.progress - event.distance) > 10:
      return 'inconsistent_geometry'
    if event.completed and event.progress < event.end:
      return 'inconsistent_completion'
    previous = self.events.get(event.event_id)
    if previous is not None:
      seq, progress, retired = previous
      if retired:
        return 'retired'
      if event.sequence <= seq or event.progress < progress:
        return 'old_event'
    elif len(self.events) >= 256:
      return 'capacity_exceeded'
    retired = event.progress >= event.end
    self.events[event.event_id] = (event.sequence, event.progress, retired)
    if retired:
      return 'completed'
    # No approach eligibility or speed decision: report geometry phase only.
    return 'before_entry' if event.progress < event.entry else 'within_ramp'
