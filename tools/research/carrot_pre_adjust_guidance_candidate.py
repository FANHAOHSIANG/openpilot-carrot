# Candidate only — NOT installed or imported by CarrotServ.
# Fixes missing guidance context only; does not establish selected exit identity.
# Baseline source blob: 06e7e78e56fefe3f34cbf486e7c8d948813a0f9a
"""Bounded Amap advisory speed; never a replacement for the posted road limit."""
from typing import Any

MAX_AGE_MS = 2000
NO_LIMIT_KPH = 250.0


def valid_target(value: Any) -> bool:
  return type(value) is int and 10 <= value <= 200 and value % 10 == 0


def pre_adjust_payload(record: dict, now_ns: int) -> tuple[int, int]:
  """Use sender-clock age plus receiver monotonic age, without clock synchronization."""
  value = record.get("value")
  value = value if isinstance(value, dict) else {}
  pre = value.get("pre_adjust")
  if not record.get("present") or not isinstance(pre, dict) or pre.get("source") != "amap_auto":
    return 0, 0
  target, generated = pre.get("target_kph"), pre.get("generated_at_ms")
  sent, received = record.get("sent_at_ms"), record.get("received_mono_ns")
  if not valid_target(target) or any(type(v) is not int or v <= 0 for v in (generated, sent, received, now_ns)):
    return 0, 0
  age = sent - generated
  if not 0 <= age < MAX_AGE_MS or now_ns < received:
    return 0, 0
  deadline = received + (MAX_AGE_MS - age) * 1_000_000
  return (target, deadline) if now_ns < deadline else (0, 0)


def pre_adjust_candidate(navi, enabled: bool, now_ns: int) -> float:
  if not enabled or navi is None or not navi.guidance_active or navi.off_route:
    return NO_LIMIT_KPH
  if not navi.session_id or not navi.route.present or not navi.current.present or navi.current.distance_m <= 0:
    return NO_LIMIT_KPH
  speed = navi.speed
  target = speed.pre_adjust_kph
  remaining = speed.pre_adjust_deadline_ns - now_ns
  if not speed.present or not valid_target(target) or not 0 < remaining <= MAX_AGE_MS * 1_000_000:
    return NO_LIMIT_KPH
  return float(target)


SOURCES = frozenset(("amap_auto", "amap_phone", "google_noo"))


def _expiry(record, generated, now_ns):
  sent, received = record.get("sent_at_ms"), record.get("received_mono_ns")
  if not record.get("present") or any(type(v) is not int or v <= 0 for v in (generated, sent, received, now_ns)):
    return 0
  age = sent - generated
  if not 0 <= age < MAX_AGE_MS or now_ns < received:
    return 0
  deadline = received + (MAX_AGE_MS - age) * 1_000_000
  return deadline if now_ns < deadline else 0


def shared_pre_adjust_payload(status_record, current_record, now_ns):
  value = status_record.get("value")
  value = value if isinstance(value, dict) else {}
  control = value.get("pre_adjust_control")
  if (not isinstance(control, dict) or control.get("source") not in SOURCES
      or control.get("enabled") is not True or value.get("guidance_active") is not True
      or value.get("off_route", False)):
    return "", 0
  # A fresh permission cannot extend an old maneuver. Both input ages count.
  status_deadline = _expiry(status_record, control.get("generated_at_ms"), now_ns)
  turn_deadline = _expiry(current_record, current_record.get("source_timestamp_ms"), now_ns)
  deadline = min(status_deadline, turn_deadline)
  return (control["source"], deadline) if deadline else ("", 0)


def shared_pre_adjust_candidate(navi, enabled, now_ns, turn_proposal):
  import math
  if (not enabled or navi is None or not navi.guidance_active or navi.off_route
      or navi.shared_pre_adjust_source not in SOURCES
      or not 0 < navi.shared_pre_adjust_deadline_ns - now_ns <= MAX_AGE_MS * 1_000_000
      or not navi.current.present or navi.current.distance_m <= 0
      or navi.current.turn_type not in (12, 13, 16, 19)):
    return NO_LIMIT_KPH
  # Shared turn pre-adjust uses the existing vehicle-side deceleration envelope,
  # not a guessed road limit, ramp target, or forced cruise-speed increase.
  return float(turn_proposal) if math.isfinite(turn_proposal) and 10 <= turn_proposal < NO_LIMIT_KPH else NO_LIMIT_KPH
