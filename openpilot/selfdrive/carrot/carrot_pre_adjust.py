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
  speed = navi.speed
  target = speed.pre_adjust_kph
  remaining = speed.pre_adjust_deadline_ns - now_ns
  if not speed.present or not valid_target(target) or not 0 < remaining <= MAX_AGE_MS * 1_000_000:
    return NO_LIMIT_KPH
  return float(target)
