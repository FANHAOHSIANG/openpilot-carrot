#!/usr/bin/env python3
"""Offline-only C4 lane/edge and navigation observation export. No control outputs."""
import argparse
import json
import math
from collections import Counter
from pathlib import Path
from gaode_lane_shadow import finite, line_points, interpolate, json_safe

DISTANCES = (10, 20, 30, 40, 60)
INTERVAL_NS = {"modelV2": 200_000_000, "carState": 200_000_000,
               "livePose": 200_000_000, "accelerometer": 200_000_000,
               "gyroscope": 200_000_000, "gpsLocation": 100_000_000,
               "gpsLocationExternal": 100_000_000, "carrotNavi": 200_000_000,
               "clocks": 0}
EPOCH_MIN_NS = 1_577_836_800_000_000_000  # 2020-01-01; reject unset clocks

def num(v):
  return v if finite(v) else None

def vector(v, limit=512):
  return [num(x) for x in list(v)[:limit]]

def fields(obj, names):
  return {k: num(getattr(obj, k, None)) for k in names}

def xy(line):
  return {k: vector(getattr(line, k, [])) for k in ("x", "y", "z", "t", "yStd")}

def points(line):
  return line_points(line["x"], line["y"])

def at(line, x):
  return interpolate(points(line), x) if line else None

def width(a, b):
  if a is None or b is None:
    return None
  w = abs(b-a)
  return w if 2.2 <= w <= 5.0 else None

def curvature(a,b,c):
  # Signed curvature of three observed local points; not a speed or steering request.
  ax,ay=a; bx,by=b; cx,cy=c
  ab=math.hypot(bx-ax,by-ay); bc=math.hypot(cx-bx,cy-by); ca=math.hypot(ax-cx,ay-cy)
  if min(ab,bc,ca)<=1e-6: return None
  return 2*((bx-ax)*(cy-ay)-(by-ay)*(cx-ax))/(ab*bc*ca)

def geometry(model):
  lines=[xy(l) for l in list(model.laneLines)[:4]]
  edges=[xy(l) for l in list(model.roadEdges)[:2]]
  probs=vector(model.laneLineProbs,4)
  lane_std=vector(getattr(model,"laneLineStds",[]),4)
  edge_std=vector(getattr(model,"roadEdgeStds",[]),2)
  def line_at(i,x):
    if i>=len(lines) or i>=len(probs) or probs[i] is None or not .65<=probs[i]<=1:
      return None
    return at(lines[i],x)
  rows=[]
  for x in DISTANCES:
    ys=[line_at(i,x) for i in range(4)]
    # Model order is outer-left, inner-left, inner-right, outer-right.
    # The sign convention is checked within each sample, never assumed from a map.
    e=[at(edges[i],x) if i<len(edges) else None for i in range(2)]
    inner=width(ys[1],ys[2])
    count=None
    center=None
    adjacent=[None,None]
    reason="inner_unavailable"
    if inner is not None:
      sign=1 if ys[2]>ys[1] else -1
      center=(ys[1]+ys[2])/2
      adjacent=[width(ys[0],ys[1]) if ys[0] is not None and (ys[1]-ys[0])*sign>0 else None,
                width(ys[2],ys[3]) if ys[3] is not None and (ys[3]-ys[2])*sign>0 else None]
      count=1+sum(w is not None for w in adjacent)
      reason="candidate"
      # Road edges have standard deviations, not lane probabilities.
      # Do not infer more lanes from road width or substitute an edge for a lane line.
      if ((e[0] is not None and len(edge_std)>0 and edge_std[0] is not None and
           0<edge_std[0]<=.5 and (e[0]-ys[1])*sign>.3) or
          (e[1] is not None and len(edge_std)>1 and edge_std[1] is not None and
           0<edge_std[1]<=.5 and (ys[2]-e[1])*sign>.3)):
        reason="road_edge_conflict"
        center=None; count=None
    rows.append({"x_m":x,"lane_y_m":ys,"edge_y_m":e,"ego_width_m":inner,
                 "center_y_m":center,"adjacent_width_m":adjacent,
                 "visible_contiguous_lane_count":count,"reason":reason})
  # Reject crossing/order reversal across sampled inner lines. No partial centreline on conflict.
  signs={1 if r["lane_y_m"][2]>r["lane_y_m"][1] else -1 for r in rows if r["ego_width_m"] is not None}
  if len(signs)>1:
    for r in rows:
      r.update(center_y_m=None,visible_contiguous_lane_count=None,reason="inner_order_reversal")
  centers=[[r["x_m"],r["center_y_m"]] for r in rows if r["center_y_m"] is not None]
  curves=[]
  # Only adjacent sample triples, not interpolated across missing data.
  for a,b,c in zip(rows,rows[1:],rows[2:]):
    if all(r["center_y_m"] is not None for r in (a,b,c)):
      k=curvature(*[(r["x_m"],r["center_y_m"]) for r in (a,b,c)])
      curves.append({"x_m":b["x_m"],"signed_curvature_1_m":k})
  meta=getattr(model,"meta",None)
  return {"frame":"c4_model_local","lane_lines":lines,"lane_probs":probs,
          "lane_stds":lane_std,"road_edges":edges,"road_edge_stds":edge_std,
          "model_path":xy(model.position),"samples":rows,"center":centers,
          "curvature":curves,"total_road_lane_count":None,
          "frame_id":num(getattr(model,"frameId",None)),
          "camera_eof_ns":num(getattr(model,"timestampEof",None)),
          "frame_drop_pct":num(getattr(model,"frameDropPerc",None)),
          "lane_change_state":str(getattr(meta,"laneChangeState","unknown")),
          "lane_change_direction":str(getattr(meta,"laneChangeDirection","unknown")),
          "vision_camera_inputs":str(getattr(model,"visionCameraInputs","unknown")),
          "vision_compute":str(getattr(model,"visionCompute","unknown"))}

def measurement(v):
  return {"valid":bool(v.valid),"xyz":fields(v,("x","y","z")),
          "std":fields(v,("xStd","yStd","zStd"))}

def item_meta(v):
  m=v.meta
  return {"present":bool(m.present),"sequence":int(m.sequence),
          "source_wall_ms":int(m.sourceTimestampMillis),
          "received_mono_ns":int(m.receivedMonoTimeNanos)}

def nav(v):
  result={"connected":bool(v.connected),"generation":int(v.generation),
          "publish_mono_ns":int(v.publishMonoTimeNanos),
          "coordinate_reference":"unverified","items":{}}
  for key,names in (
      ("vehicle",("latitude","longitude","headingDeg","speedKph")),
      ("guidanceCurrent",("distanceM","turnType")),
      ("guidanceNext",("distanceM","turnType")),
      ("laneCurrent",("count","currentLane","distanceM","turnCode")),
      ("route",("remainingDistanceM","totalDistanceM"))):
    obj=getattr(v,key)
    m=item_meta(obj)
    item={"meta":m}
    # Never convert default values of missing items into observations.
    if m["present"]:
      item.update(fields(obj,names))
      if key=="laneCurrent":
        item.update(visible=bool(obj.visible),turn_info=vector(obj.turnInfo,64),
                    available=vector(obj.available,64))
      if key=="route": item["point_count"]=len(obj.polyline)
    result["items"][key]=item
  return result

def decode(kind,v):
  if kind=="modelV2": return geometry(v)
  if kind in ("gpsLocation","gpsLocationExternal"):
    return {**fields(v,("latitude","longitude","altitude","speed","bearingDeg",
                         "horizontalAccuracy","verticalAccuracy","bearingAccuracyDeg",
                         "unixTimestampMillis","satelliteCount","flags")),
            "has_fix":bool(v.hasFix),"source":str(v.source),"coordinate_reference":"WGS84"}
  if kind=="livePose":
    return {"timestamp":int(v.timestamp),"inputs_ok":bool(v.inputsOK),
            "posenet_ok":bool(v.posenetOK),"sensors_ok":bool(v.sensorsOK),
            **{k:measurement(getattr(v,k)) for k in ("orientationNED","velocityDevice",
              "accelerationDevice","angularVelocityDevice")}}
  if kind=="carState":
    return {**fields(v,("vEgo","aEgo","yawRate","steeringAngleDeg")),
            "can_valid":bool(v.canValid),"left_blinker":bool(v.leftBlinker),
            "right_blinker":bool(v.rightBlinker)}
  if kind in ("accelerometer","gyroscope"):
    union=v.which()
    return {"sensor_timestamp":int(v.timestamp),"source":str(v.source),
            "measurement":union,"xyz":vector(getattr(getattr(v,union),"v",[]),3)}
  if kind=="clocks": return {"wall_ns":int(v.wallTimeNanos)}
  if kind=="carrotNavi": return nav(v)
  raise ValueError(kind)

def records(messages,segment_index):
  """Independent per-segment state; no extrapolation across segments or clock resets."""
  last={}
  last_clock=None
  last_t=-1
  stats=Counter()
  for msg in messages:
    kind=msg.which()
    if kind not in INTERVAL_NS: continue
    t=int(msg.logMonoTime)
    if t<last_t:
      last.clear();last_clock=None
      stats["clock_reset"]+=1
    last_t=t
    if not msg.valid:
      # Expose validity gaps without flooding the output.
      stats[kind+":invalid"]+=1
      if kind=="clocks": last_clock=None
      continue
    if kind in last and t-last[kind]<INTERVAL_NS[kind]:continue
    last[kind]=t
    data=decode(kind,getattr(msg,kind))
    if kind=="clocks":
      wall=data["wall_ns"]
      last_clock=(t,wall) if wall>=EPOCH_MIN_NS else None
    # A C4-local clock estimate is not proof of Android clock alignment.
    wall_est=None; clock_age=None
    if last_clock and 0<=t-last_clock[0]<=15_000_000_000:
      clock_age=t-last_clock[0]
      wall_est=last_clock[1]+clock_age
    stats[kind]+=1
    yield {"schema":2,"segment_index":segment_index,"kind":kind,"mono_ns":t,
           "clock":"c4_log_mono_ns","wall_est_ns":wall_est,"clock_anchor_age_ns":clock_age,
           "phone_clock_alignment_verified":False,"control_usable":False,"data":data}
  yield {"schema":2,"segment_index":segment_index,"kind":"segment_summary",
         "counts":dict(stats),"control_usable":False}

def main():
  p=argparse.ArgumentParser(description=__doc__)
  p.add_argument("--rlog",nargs="+",required=True,help="Local full rlog file(s), in route order")
  p.add_argument("--out",required=True,help="New JSONL file; refuses overwrite")
  a=p.parse_args()
  if len(a.rlog)>300:p.error("maximum 300 segments")
  paths=[Path(x) for x in a.rlog]
  if any(not x.is_file() for x in paths):p.error("only existing local full rlogs")
  from tools.lib.logreader import LogReader
  with open(a.out,"x",encoding="utf-8") as f:
    for i,path in enumerate(paths):
      for row in records(LogReader(str(path),sort_by_time=True),i):
        f.write(json.dumps(json_safe(row),allow_nan=False,separators=(",",":"))+"\n")
      f.flush()

if __name__=="__main__":main()
