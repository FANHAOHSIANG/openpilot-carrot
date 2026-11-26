#!/usr/bin/env python3
"""Read-only modelV2 lane geometry observer. Never publishes to vehicle buses."""
import argparse
import bisect
import json
import math
import time
from pathlib import Path

DISTANCES = (10, 20, 30, 40, 60)
def finite(x):
  return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)

def line_points(x, y):
  if len(x) != len(y) or not 2 <= len(x) <= 512:
    return None
  pts = list(zip(x, y))
  if any(not finite(a) or not finite(b) or abs(b) > 100 or abs(a) > 500 for a,b in pts):
    return None
  if any(b[0] <= a[0] for a,b in zip(pts,pts[1:])):
    return None
  return pts

def interpolate(points, x):
  if not points or x < points[0][0] or x > points[-1][0]:
    return None
  i = bisect.bisect_left([p[0] for p in points], x)
  if points[i][0] == x:
    return points[i][1]
  a,b = points[i-1],points[i]
  return a[1] + (b[1]-a[1])*(x-a[0])/(b[0]-a[0])

def visual(model, mono_ns):
  out = {"schema":1,"source":"c4_modelV2","mono_ns":int(mono_ns),
         "frame":"c4_model_local","control_usable":False,"center":[],"reason":"unavailable"}
  lines,probs = list(model.laneLines),list(model.laneLineProbs)
  out["lane_lines"] = [{"x":list(l.x),"y":list(l.y)} for l in lines[:4]]
  out["lane_probs"] = [float(p) if finite(p) else None for p in probs[:4]]
  out["road_edges"] = [{"x":list(l.x),"y":list(l.y)} for l in list(model.roadEdges)[:2]]
  out["model_path"] = {"x":list(model.position.x),"y":list(model.position.y)}
  if len(lines)!=4 or len(probs)!=4 or any(not finite(probs[i]) or probs[i]<.65 for i in (1,2)):
    out["reason"]="inner_lane_confidence"; return out
  a,b = [line_points(list(lines[i].x),list(lines[i].y)) for i in (1,2)]
  if not a or not b:
    out["reason"]="invalid_geometry"; return out
  center=[]
  for x in DISTANCES:
    u,v=interpolate(a,x),interpolate(b,x)
    if u is None or v is None: continue
    if not 2.2 <= abs(u-v) <= 5.0:
      out["reason"]="implausible_width"; return out
    center.append([x,(u+v)/2])
  if len(center)<2:
    out["reason"]="short_overlap"; return out
  out["center"]=center;out["reason"]="visual_candidate"
  return out

def compare(v,m):
  out={"control_usable":False,"status":"map_unavailable","samples":[]}
  if not m: return out
  # A separate, verified alignment stage must provide this local-frame geometry.
  # Never apply a guessed coordinate transform, or interpret raw lat/lon as metres.
  if (m.get("frame")!="c4_model_local" or m.get("clock")!="c4_monotonic_ns"
      or m.get("alignment_verified") is not True or m.get("source")!="gaode_native_centerline"):
    out["status"]="alignment_unverified"; return out
  ts=m.get("mono_ns")
  if not isinstance(ts,int) or isinstance(ts,bool) or abs(ts-v["mono_ns"])>200_000_000:
    out["status"]="time_mismatch"; return out
  raw=m.get("points")
  if not isinstance(raw,list) or any(not isinstance(p,list) or len(p)!=2 for p in raw):
    out["status"]="map_invalid";return out
  pts=line_points([p[0] for p in raw],[p[1] for p in raw])
  if not pts: out["status"]="map_invalid";return out
  for x,y in v["center"]:
    z=interpolate(pts,x)
    if z is not None: out["samples"].append({"x_m":x,"delta_y_m":round(z-y,3)})
  out["status"]="compared" if out["samples"] else "no_overlap"
  return out

def json_safe(v):
  if isinstance(v,float) and not math.isfinite(v): return None
  if isinstance(v,list): return [json_safe(x) for x in v]
  if isinstance(v,dict): return {k:json_safe(x) for k,x in v.items()}
  return v

def main():
  p=argparse.ArgumentParser(description=__doc__)
  mode=p.add_mutually_exclusive_group(required=True)
  mode.add_argument("--live",action="store_true")
  mode.add_argument("--rlog")
  p.add_argument("--out",required=True)
  p.add_argument("--seconds",type=int,default=60)
  p.add_argument("--map-jsonl",help="Offline only: independently verified, C4-local aligned map samples")
  a=p.parse_args()
  if a.live and a.map_jsonl: p.error("Map comparison is offline only")
  if not 1<=a.seconds<=600:p.error("seconds must be 1..600")
  maps={}
  if a.map_jsonl:
    with open(a.map_jsonl) as f:
      for i,line in enumerate(f):
        if i>=100000: raise ValueError("map record limit")
        m=json.loads(line)
        if isinstance(m,dict) and isinstance(m.get("mono_ns"),int):maps[m["mono_ns"]]=m
  times=sorted(maps)
  def nearest(t):
    i=bisect.bisect_left(times,t)
    candidates=times[max(0,i-1):i+1]
    return maps[min(candidates,key=lambda n:abs(n-t))] if candidates else None
  def emit(f,model,t):
    v=visual(model,t)
    v["comparison"]=compare(v,nearest(t))
    f.write(json.dumps(json_safe(v),allow_nan=False,separators=(",",":"))+"\n")
  with open(a.out,"x",encoding="utf-8") as f:
    if a.live:
      import cereal.messaging as messaging
      sm=messaging.SubMaster(["modelV2"],poll="modelV2")
      end=time.monotonic()+a.seconds;last=0
      while time.monotonic()<end:
        sm.update(500)
        t=int(sm.logMonoTime["modelV2"])
        if sm.updated["modelV2"] and sm.valid["modelV2"] and t-last>=200_000_000:
          emit(f,sm["modelV2"],t);last=t
        f.flush()
    else:
      from tools.lib.logreader import LogReader
      last=0
      for msg in LogReader(a.rlog):
        t=int(msg.logMonoTime)
        if msg.which()=="modelV2" and msg.valid and t-last>=200_000_000:
          emit(f,msg.modelV2,t);last=t
if __name__=="__main__":main()
