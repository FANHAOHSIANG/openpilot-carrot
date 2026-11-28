"""PRE-only advisory filtering and non-actuating transition preview.

The connection session is not a route identity. A rejected advisory cannot be
re-authorized just because ego speed changes; keep the latch for that session.
No independent speed source is filtered here. Preview values are not commands.
"""
import math

NO_LIMIT_KPH = 250.0
GAP_LIMIT = 0.20


def _speed(value):
  return type(value) in (int, float) and math.isfinite(value) and value >= 0


class PreAdvisoryGuard:
  def __init__(self):
    self.session = None
    self.blocked = False
    self.reason = 'inactive'

  def admit(self, session, ego_kph, target_kph):
    if not isinstance(session, str) or not session:
      self.reason = 'no_session'
      return NO_LIMIT_KPH
    if session != self.session:
      self.session, self.blocked = session, False
    if not _speed(target_kph) or not 10 <= target_kph < NO_LIMIT_KPH:
      self.reason = 'inactive'
      return NO_LIMIT_KPH
    if self.blocked:
      self.reason = 'session_latched'
      return NO_LIMIT_KPH
    if not _speed(ego_kph) or ego_kph <= 0:
      self.reason = 'ego_unavailable'
      return NO_LIMIT_KPH
    if abs(target_kph - ego_kph) > GAP_LIMIT * ego_kph + 1e-9:
      self.blocked = True
      self.reason = 'gap_over_20pct'
      return NO_LIMIT_KPH
    self.reason = 'within_gap_not_exit_verified'
    return float(target_kph)


class PreTransitionPreview:
  """Non-actuating reference: never prolong a withdrawn PRE or relax another cap.

  Rates are illustrative replay parameters, not calibrated vehicle settings.
  """
  def __init__(self):
    self.key = self.value = self.last_ns = None

  def reset(self):
    self.key = self.value = self.last_ns = None

  def step(self, key, now_ns, ego_kph, target_kph, other_cap):
    if (not key or type(now_ns) is not int or now_ns <= 0
        or not all(_speed(v) for v in (ego_kph, target_kph, other_cap))
        or not 10 <= target_kph < NO_LIMIT_KPH):
      self.reset()
      return None
    if key != self.key or self.last_ns is None or not 0 < now_ns - self.last_ns <= 1_000_000_000:
      self.key, self.value, self.last_ns = key, min(ego_kph, other_cap), now_ns
      return self.value
    dt = (now_ns - self.last_ns) / 1e9
    self.value = min(other_cap, min(self.value + 2 * dt, max(self.value - 3 * dt, target_kph)))
    self.last_ns = now_ns
    return self.value
