"""Bounded AMap recommendation candidates for observation only, never control."""
import json
from .amap_exit_display import _deadline

TTL_NS = 2_000_000_000
EMPTY = {"valid": False, "deadlineMonoTimeNanos": 0, "fieldsJson": ""}

def _dict(v):
  return v if type(v) is dict else {}

def _int(v, limit):
  return type(v) is int and 0 <= v <= limit

def lane_display_payload(snapshot, now):
  if snapshot.get("connected") is not True:
    return dict(EMPTY)
  items = _dict(snapshot.get("items"))
  guide, status = _dict(items.get("guidance_current")), _dict(items.get("navigation_status"))
  sv = _dict(status.get("value"))
  if guide.get("present") is not True or sv.get("guidance_active") is not True or sv.get("off_route", False) is not False:
    return dict(EMPTY)
  info = _dict(_dict(guide.get("value")).get("amap_lane_candidate"))
  if type(info.get("version")) is not int or info["version"] != 1 or info.get("scope") != "display_only":
    return dict(EMPTY)
  generated, stamp = info.get("generated_at_ms"), guide.get("source_timestamp_ms")
  if any(type(x) is not int or x <= 0 for x in (generated, stamp)) or abs(generated-stamp) > 1000:
    return dict(EMPTY)
  deadline = min(_deadline(guide, generated, now), _deadline(guide, stamp, now),
                 _deadline(status, status.get("source_timestamp_ms"), now))
  if not 0 < deadline-now <= TTL_NS:
    return dict(EMPTY)
  c = _dict(info.get("candidate"))
  source, n, rows = c.get("source"), c.get("count"), c.get("lanes")
  if source not in ("amap_auto_13012", "amap_link_14") or c.get("control_input") is not False or c.get("absolute_mapping_verified") is not False or c.get("absolute_lane_index") is not None:
    return dict(EMPTY)
  if not _int(n,32) or n < 1 or type(rows) is not list or len(rows) != n:
    return dict(EMPTY)
  out=[]
  for i,r in enumerate(rows):
    r = _dict(r)
    index, back, front, advice = (r.get(k) for k in ("index","back_code","front_code","advised"))
    if type(index) is not int or index != i or not _int(back,65535 if source=="amap_auto_13012" else 255):
      return dict(EMPTY)
    if "advised" not in r or (advice is not None and type(advice) is not bool):
      return dict(EMPTY)
    if source=="amap_auto_13012":
      if front is not None:
        return dict(EMPTY)
    elif not _int(front,255) or advice is not (front != 255):
      return dict(EMPTY)
    out.append({"index":i,"back_code":back,"front_code":front,"advised":advice})
  age=info.get("observation_age_ms")
  observed=info.get("observed_at_ms")
  if age is not None or observed is not None:
    max_age=180000 if source=="amap_auto_13012" else 2000
    if not _int(age,max_age-1) or type(observed) is not int or observed<=0:
      return dict(EMPTY)
    if not -1000 <= generated-observed < max_age or abs((generated-observed)-age)>2500:
      return dict(EMPTY)
    deadline=min(deadline, now+(max_age-age)*1000000)
  fields={"source":source,"count":n,"lanes":out,"absolute_mapping_verified":False,"control_input":False}
  if age is not None:
    fields["observation_age_ms"]=age
  return {"valid":True,"deadlineMonoTimeNanos":deadline,"fieldsJson":json.dumps(fields,separators=(",",":"))}

def candidate_count(raw):
  """Only neutral aggregate counts for display, not physical lane positions."""
  if type(raw) is not str or not 0 < len(raw) <= 8192:
    return None
  try:
    c=json.loads(raw)
    if type(c) is not dict or c.get("source") not in ("amap_auto_13012","amap_link_14") or c.get("control_input") is not False or c.get("absolute_mapping_verified") is not False:
      return None
    n,rows=c.get("count"),c.get("lanes")
    if not _int(n,32) or n<1 or type(rows) is not list or len(rows)!=n:
      return None
    if any(type(r) is not dict or type(r.get("index")) is not int or r["index"]!=i or "advised" not in r or (r["advised"] is not None and type(r["advised"]) is not bool) for i,r in enumerate(rows)):
      return None
    return (sum(r["advised"] is True for r in rows),n,sum(r["advised"] is None for r in rows))
  except (ValueError,TypeError,RecursionError):
    return None
