#!/usr/bin/env python3
"""Offline diagnostic comparison only. No control, bus, or device actions."""
import argparse
import json
from collections import Counter, deque
from statistics import median
from gaode_lane_shadow import line_points, interpolate
from gaode_vision_export import geometry

HORIZONS = (10, 20, 30)
MAX_GAP = 400_000_000
MEM_TTL = 1_000_000_000
CAR_TTL = 250_000_000


def candidate_rows(d):
  return {r['x_m']: r for r in d['samples'] if r['x_m'] in HORIZONS}


def path_samples(d):
  pts = line_points(d['model_path']['x'], d['model_path']['y'])
  vals = [interpolate(pts, x) for x in HORIZONS]
  return vals if all(v is not None for v in vals) else None


def edge_check(d, rows, vals, sign=None):
  """Only low-std edges are considered; not a probability or ground truth."""
  if vals is None or sign not in (-1, 1):
    return 'unverified'
  std = d['road_edge_stds']
  reliable = [i < len(std) and std[i] is not None and 0 < std[i] <= .5 and
              all(rows[x]['edge_y_m'][i] is not None for x in HORIZONS) for i in range(2)]
  for x, y in zip(HORIZONS, vals):
    left, right = rows[x]['edge_y_m']
    if ((reliable[0] and (y-left)*sign < .5) or
        (reliable[1] and (right-y)*sign < .5)):
      return 'conflict'
  return 'two_edges' if all(reliable) else 'one_edge' if any(reliable) else 'unverified'


class Shadow:
  def __init__(self):
    self.memory = deque(maxlen=3)
    self.last_t = None
    self.car = None
    self.prev = None
    self.last_single_side = None

  def reset(self):
    self.memory.clear()
    self.prev = None
    self.last_single_side = None

  def observe_car(self, msg):
    v = msg.carState
    self.car = (int(msg.logMonoTime), bool(msg.valid and v.canValid),
                bool(v.leftBlinker or v.rightBlinker), float(v.vEgo) if hasattr(v, "vEgo") else None)
    if not self.car[1] or self.car[2]:
      self.reset()

  def evaluate(self, d, t):
    if self.last_t is not None and not 0 < t-self.last_t <= MAX_GAP:
      self.reset()
    self.last_t = t
    rows = candidate_rows(d)
    native = path_samples(d)
    change = d['lane_change_state'] != 'off' or d['lane_change_direction'] != 'none'
    car_ok = self.car is not None and 0 <= t-self.car[0] <= CAR_TTL and self.car[1] and not self.car[2]
    if change or not car_ok:
      self.reset()
    out = {'schema': 1, 'mono_ns': t, 'control_usable': False,
           'map_alignment_verified': False, 'native_path_y_m': native,
           'candidate_y_m': None, 'source': 'none', 'reason': 'no_valid_candidate',
           'edge_check': 'unverified', 'memory_age_ms': None,
           'memory_width_m': None, 'native_delta_max_m': None,
           'raw_frame_delta_max_m': None,
           'speed_mps': self.car[3] if car_ok else None,
           'native_path_status': 'available' if native is not None else 'insufficient_30m_geometry'}
    if len(rows) != len(HORIZONS):
      self.reset(); return out
    dual = [rows[x]['center_y_m'] for x in HORIZONS]
    widths = [rows[x]['ego_width_m'] for x in HORIZONS]
    signs = {1 if rows[x]['lane_y_m'][2] > rows[x]['lane_y_m'][1] else -1
             for x in HORIZONS if rows[x]['center_y_m'] is not None}
    sign = next(iter(signs)) if len(signs) == 1 else None
    conflict = any(rows[x]['reason'] in ('road_edge_conflict', 'inner_order_reversal') for x in HORIZONS)
    if conflict:
      self.reset()
      out['reason'] = 'geometry_conflict'
    elif all(y is not None for y in dual) and sign is not None:
      out.update(source='dual_line', candidate_y_m=dual, reason='observed_center',
                 edge_check=edge_check(d, rows, dual, sign))
      self.last_single_side = None
      # Memory stores only widths, never a world position or previous path.
      w = median(widths)
      if car_ok and not change and max(widths)-min(widths) <= .35 and native is not None and max(abs(a-b) for a,b in zip(dual,native)) <= .6:
        if self.memory and (self.memory[-1][2] != sign or abs(self.memory[-1][1]-w) > .3 or t-self.memory[-1][0] > MAX_GAP):
          self.memory.clear()
        self.memory.append((t,w,sign))
      else:
        self.memory.clear()
    else:
      # Rejected two-sided geometry must not be reinterpreted as a missing side.
      rejected = any(rows[x]['lane_y_m'][1] is not None and rows[x]['lane_y_m'][2] is not None for x in HORIZONS)
      sides = [i for i in (1,2) if all(rows[x]['lane_y_m'][i] is not None and rows[x]['lane_y_m'][3-i] is None for x in HORIZONS)]
      if rejected:
        self.reset(); out['reason'] = 'dual_geometry_rejected'
      elif not sides or (self.last_single_side is not None and sides[0] != self.last_single_side):
        self.reset(); out['reason'] = 'single_side_not_consistent'
      elif len(self.memory) == 3 and car_ok and not change and 0 <= t-self.memory[-1][0] <= MEM_TTL and len(sides) == 1:
        age = t-self.memory[-1][0]
        w = median(v[1] for v in self.memory)
        s = self.memory[-1][2]
        out.update(memory_age_ms=age/1e6, memory_width_m=w)
        vals = [rows[x]['lane_y_m'][sides[0]] + (s*w/2 if sides[0] == 1 else -s*w/2) for x in HORIZONS]
        check = edge_check(d, rows, vals, s)
        if native is not None and max(abs(a-b) for a,b in zip(vals,native)) <= .6 and check in ('one_edge','two_edges'):
          out.update(source='single_line_memory',candidate_y_m=vals,reason='short_memory_agrees',edge_check=check)
          self.last_single_side = sides[0]
        else:
          out.update(reason='memory_crosscheck_failed',edge_check=check)
          self.memory.clear()
      else:
        if self.memory and t-self.memory[-1][0] > MEM_TTL: out['reason']='memory_expired'
        elif self.memory: out['reason']='memory_not_ready'
        self.reset()
    # Native path remains a separate reference, never called a lane center.
    # For two-edge corroboration infer order only from contemporaneous edge pairs.
    if out['source'] == 'none' and native is not None:
      es = [rows[x]['edge_y_m'] for x in HORIZONS]
      signs = {1 if r[1]>r[0] else -1 for r in es if None not in r and r[0]!=r[1]}
      direction = next(iter(signs)) if len(signs)==1 and all(None not in r and r[0]!=r[1] for r in es) else None
      check = edge_check(d,rows,native,direction)
      out['edge_check'] = check
      out['source'] = ('native_two_edge_reference' if check == 'two_edges' else
                       'native_edge_conflict_reference' if check == 'conflict' else 'native_unverified_reference')
    vals = out['candidate_y_m']
    if vals is not None:
      if native is not None: out['native_delta_max_m'] = max(abs(a-b) for a,b in zip(vals,native))
      if self.prev is not None: out['raw_frame_delta_max_m'] = max(abs(a-b) for a,b in zip(vals,self.prev))
    self.prev = vals
    return out


def replay(messages):
  state = Shadow(); last = None; prior_t = None
  for msg in messages:
    kind = msg.which()
    if kind not in ('carState','modelV2'): continue
    t = int(msg.logMonoTime)
    if prior_t is not None and t < prior_t:
      state = Shadow(); last = None
    prior_t=t
    if kind == 'carState': state.observe_car(msg); continue
    if not msg.valid:
      state.reset(); state.last_t=None; continue
    # Observe change on every frame, not only sampled frames.
    meta=msg.modelV2.meta
    if str(meta.laneChangeState) != 'off' or str(meta.laneChangeDirection) != 'none': state.reset()
    if last is not None and t-last < 200_000_000: continue
    last = t
    yield state.evaluate(geometry(msg.modelV2),t)


def summarize(rows):
  counts=Counter(r['source'] for r in rows)
  reasons=Counter(r['reason'] for r in rows)
  def values(k, source): return [r[k] for r in rows if r['source']==source and r[k] is not None]
  def stats(v):
    v=sorted(v)
    return {'n':len(v),'median':median(v) if v else None,'p95':v[min(len(v)-1,int(.95*len(v)))] if v else None,'max':max(v) if v else None}
  return {'sample_count':len(rows),'sources':dict(counts),'reasons':dict(reasons),
          'edge_checks':dict(Counter(r['edge_check'] for r in rows)),
          'native_delta_m':{s:stats(values('native_delta_max_m',s)) for s in ('dual_line','single_line_memory')},
          'raw_frame_delta_m':{s:stats(values('raw_frame_delta_max_m',s)) for s in ('dual_line','single_line_memory')},
          'control_usable':False,'accuracy_verified':False}


def main():
  p=argparse.ArgumentParser(description=__doc__)
  p.add_argument('--rlog',nargs='+',required=True);p.add_argument('--out',required=True)
  a=p.parse_args()
  from tools.lib.logreader import LogReader
  with open(a.out,'x',encoding='utf-8') as f:
    for i,path in enumerate(a.rlog):
      rows=list(replay(LogReader(path,sort_by_time=True)))
      f.write(json.dumps({'segment_index':i,**summarize(rows)},allow_nan=False)+'\n')
if __name__=='__main__': main()
