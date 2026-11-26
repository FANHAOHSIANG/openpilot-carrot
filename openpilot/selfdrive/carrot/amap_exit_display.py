"""Untrusted Amap Auto metadata for display consumers only; not control input."""
import json

MAX_AGE_MS = 2000
MATCH_MS = 500
TEXT = ("EXIT_NAME_INFO", "EXIT_DIRECTION_INFO", "SEG_REMAIN_DIS_AUTO", "CUR_ROAD_NAME", "NEXT_ROAD_NAME", "ROUTE_REMAIN_DIS_AUTO", "ROUTE_REMAIN_TIME_AUTO")
NUMERIC = ("SEG_REMAIN_DIS", "CUR_SEG_NUM", "CUR_POINT_NUM", "ROAD_TYPE", "ICON", "CAR_DIRECTION", "NEW_ICON", "ROUTE_REMAIN_DIS", "ROUTE_ALL_DIS", "ROUTE_REMAIN_TIME")


def _dict(value):
  return value if isinstance(value, dict) else {}


def _deadline(record, generated, now):
  sent, received = record.get("sent_at_ms"), record.get("received_mono_ns")
  if record.get("present") is not True or any(type(v) is not int or v <= 0 for v in (sent, received, generated, now)):
    return 0
  age = sent - generated
  if not 0 <= age < MAX_AGE_MS or now < received:
    return 0
  deadline = received + (MAX_AGE_MS - age) * 1000000
  return deadline if now < deadline else 0


def _text(value, maximum):
  if type(value) is not str or not value.strip() or len(value) > maximum:
    return None
  if any(ord(c) < 32 or ord(c) == 127 or 0xd800 <= ord(c) <= 0xdfff for c in value):
    return None
  return value


def _number(value):
  return type(value) is int and 0 <= value <= 2000000


def amap_exit_display_payload(snapshot, now):
  """Publish only bounded raw fields; no lane, ramp, speed or steering inference."""
  empty = {"valid": False, "deadlineMonoTimeNanos": 0, "fieldsJson": ""}
  if snapshot.get("connected") is not True:
    return empty
  items = _dict(snapshot.get("items"))
  guidance, status = _dict(items.get("guidance_current")), _dict(items.get("navigation_status"))
  status_value = _dict(status.get("value"))
  if status_value.get("guidance_active") is not True or status_value.get("off_route", False) is not False:
    return empty
  info = _dict(_dict(guidance.get("value")).get("amap_exit_info"))
  if info.get("source") != "amap_auto" or info.get("scope") != "display_only":
    return empty
  generated, stamp = info.get("generated_at_ms"), guidance.get("source_timestamp_ms")
  if any(type(v) is not int or v <= 0 for v in (generated, stamp)) or abs(generated - stamp) > MATCH_MS:
    return empty
  deadline = min(_deadline(guidance, generated, now), _deadline(guidance, stamp, now),
                 _deadline(status, status.get("source_timestamp_ms"), now))
  if deadline <= now:
    return empty
  raw, fields = _dict(info.get("fields")), {}
  for key in TEXT:
    value = _text(raw.get(key), 160)
    if value is not None:
      fields[key] = value
  for key in (*NUMERIC, "EXIT_DIRECTION_INFO"):
    if _number(raw.get(key)):
      fields[key] = raw[key]
  lane = raw.get("EXTRA_DRIVE_WAY")
  if _text(lane, 256) is not None:
    fields["EXTRA_DRIVE_WAY"] = lane
  elif type(lane) is list and 0 < len(lane) <= 32 and all(type(i) is int and -(2**31) <= i < 2**31 for i in lane):
    fields["EXTRA_DRIVE_WAY"] = lane
  if not fields:
    return empty
  return {"valid": True, "deadlineMonoTimeNanos": deadline,
          "fieldsJson": json.dumps(fields, ensure_ascii=True, separators=(",", ":"))}
