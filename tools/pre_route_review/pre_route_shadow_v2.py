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
    self.retired_sessions = set()

  def observe(self, context, event):
    if (not isinstance(context.session, str) or not context.session or
        not isinstance(context.route, str) or not context.route or
        type(context.revision) is not int or context.revision < 0 or type(context.active) is not bool):
      return 'invalid_context'
    # Context must be supplied independently by an authoritative route source.
    if context.session in self.retired_sessions:
      return 'old_session'
    if self.context is not None:
      if context.session == self.context.session:
        if (context.revision < self.context.revision or
            (context.revision == self.context.revision and context.route != self.context.route) or
            (context.revision == self.context.revision and context.active and not self.context.active)):
          return 'old_context'
      else:
        if len(self.retired_sessions) >= 256:
          return 'session_capacity_exceeded'
        self.retired_sessions.add(self.context.session)
    if self.context != context:
      self.context = context
      self.events.clear()
    # Record stop even if no event is supplied; an old active snapshot cannot revive it.
    if not context.active:
      return 'no_guidance'
    if event is None or (event.session, event.route, event.revision) != (context.session, context.route, context.revision):
      return 'not_current_route'
    if not isinstance(event.event_id, str) or not event.event_id or type(event.sequence) is not int or event.sequence < 0:
      return 'invalid_identity'
    if event.kind not in ('exit', 'merge', 'interchange'):
      return 'not_ramp'
    values = (event.progress, event.entry, event.end, event.distance, event.age_ms)
    if not all(type(v) in (int, float) and isfinite(v) for v in values):
      return 'invalid_geometry'
    if type(event.matched) is not bool or not event.matched or not 0 <= event.age_ms < 2000:
      return 'unverified_position'
    if type(event.completed) is not bool or not 0 <= event.entry < event.end or event.progress < 0 or abs(event.entry - event.progress - event.distance) > 10:
      return 'inconsistent_geometry'
    if event.completed and event.progress < event.end:
      return 'inconsistent_completion'
    geometry = (event.kind, event.entry, event.end)
    previous = self.events.get(event.event_id)
    if previous is not None:
      seq, progress, retired, previous_geometry = previous
      if retired:
        return 'retired'
      if geometry != previous_geometry:
        return 'changed_event_geometry'
      if event.sequence <= seq or event.progress < progress:
        return 'old_event'
    elif len(self.events) >= 256:
      return 'capacity_exceeded'
    retired = event.progress >= event.end
    self.events[event.event_id] = (event.sequence, event.progress, retired, geometry)
    if retired:
      return 'completed'
    # No approach eligibility or speed decision: report geometry phase only.
    return 'before_entry' if event.progress < event.entry else 'within_ramp'
