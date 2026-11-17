"""Synthetic closed-loop falsification, NOT a neural-model or Ioniq5 simulator.

A: analytic biased preview driver, original pinned 100 Hz scalar limits.
C: existing relative-geometry proposal with the same limits.
U: uncertainty-bounded experimental proposal with the same limits.
Each arm evolves its own pose. B (actual lane-mode planner) is NOT implemented.
Never promote a candidate solely from these results.
"""
import argparse
from collections import Counter, deque
from dataclasses import asdict, dataclass
import itertools
import json
import math
from pathlib import Path

from openpilot.tools.curve_centering.centering_shadow import CenteringShadow
from openpilot.tools.curve_centering.model_baseline import model_step, SOURCE_COMMIT
from openpilot.tools.curve_centering.uncertainty_shadow import GeometryBound, UncertaintyShadow

DT = 0.01
DURATION = 30.0


@dataclass(frozen=True)
class Scenario:
  speed: float = 12.0
  peak_curvature: float = 0.02
  direction: int = 1
  model_bias: float = 0.3
  differential_error: float = 0.0
  delay: float = 0.1
  lag: float = 0.15
  authority_accel: float = 3.0
  assumed_error_bound: float = 0.2
  fault: str = 'none'

  def __post_init__(self):
    numeric = (self.speed, self.peak_curvature, self.model_bias, self.differential_error,
               self.delay, self.lag, self.authority_accel, self.assumed_error_bound)
    if (not all(math.isfinite(x) for x in numeric) or self.speed <= 0 or self.peak_curvature < 0
        or self.delay < 0 or self.lag <= 0 or self.authority_accel <= 0 or self.assumed_error_bound < 0
        or self.direction not in (-1, 1) or self.fault not in ('none', 'line_loss', 'stale', 'takeover')):
      raise ValueError('invalid scenario')


def road_curvature(t, scenario):
  # Road is a synthetic time-indexed curvature profile, not mapped route geometry.
  if t < 5 or t >= 23:
    scale = 0.0
  elif t < 10:
    scale = (1-math.cos(math.pi*(t-5)/5))/2
  elif t <= 18:
    scale = 1.0
  else:
    scale = (1+math.cos(math.pi*(t-18)/5))/2
  return scenario.direction * scenario.peak_curvature * scale


def run(scenario, arm='A', *, gain=0.5, retain_trace=False):
  if arm not in ('A', 'C', 'U'):
    raise ValueError('unsupported comparison arm')
  shadow = CenteringShadow() if arm == 'C' else UncertaintyShadow(gain=gain)
  bound = GeometryBound(scenario.assumed_error_bound, 20.0, 0.0, DURATION, 'synthetic-assumption-only')
  y = heading = actual = command = held = 0.0
  queue = deque([0.0] * round(scenario.delay/DT))
  squared = peak = exit_peak = max_rate = 0.0
  saturated = limited = samples = 0
  counts = Counter()
  trace = []
  valid = True
  for i in range(round(DURATION/DT)):
    t = i*DT
    road = road_curvature(t, scenario)
    fault = scenario.fault if 12 <= t < 15 else 'none'
    takeover = fault == 'takeover'
    # Analytic preview surrogate. No actual small/large model is loaded here.
    if i % 5 == 0:
      action = road - 2*(y+20*heading-scenario.model_bias)/20**2
      raw_error = y+20*heading+20**2*(action-road)/2+scenario.differential_error
      row = {'model_t':t if fault != 'stale' else t-1.0,
             'model_action_curvature':action, 'speed_kph':scenario.speed*3.6,
             'eligible':fault == 'none', 'reasons':[] if fault == 'none' else [fault],
             'driver_pressed':takeover, 'lat_active':not takeover, 'lane_change_state':'off',
             'desire':'none', 'lateral_accel_error_mps2':(command-actual)*scenario.speed**2,
             'steering_saturated':abs(command)*scenario.speed**2 >= scenario.authority_accel,
             'use_lane_lines':False,
             'geometry':None if fault == 'line_loss' else {'samples':[{'x_m':20.0, 'raw_error_m':raw_error}]}}
      result = None if arm == 'A' else (shadow.update(row) if arm == 'C' else shadow.update(row, bound))
      held = action if result is None else result['proposal_curvature']
      if result is not None:
        counts.update(result['reasons'])
    # Same idealized human surrogate in all arms; not a physical handover model.
    request = road - 2*(y+20*heading)/20**2 if takeover else held
    previous = command
    step = model_step(speed=scenario.speed, previous=previous, action=request, feedback=actual,
                      roll=0.0, active=True, lateral_started=True)
    command = step.curvature
    max_rate = max(max_rate, abs(command-previous)/DT)
    limited += step.rate_limited
    queue.append(command)
    delayed = queue.popleft()
    cap = scenario.authority_accel/scenario.speed**2
    actuator_target = max(-cap, min(cap, delayed))
    saturated += abs(delayed) >= cap
    actual += (1-math.exp(-DT/scenario.lag))*(actuator_target-actual)
    denominator = 1-road*y
    if denominator <= 0.2 or abs(heading) > 1.2 or abs(y) > 10:
      valid = False
      counts['plant_domain_exceeded'] += 1
      break
    y += scenario.speed*math.sin(heading)*DT
    heading += scenario.speed*(actual-road*math.cos(heading)/denominator)*DT
    squared += y*y
    peak = max(peak, abs(y))
    if t >= 18:
      exit_peak = max(exit_peak, abs(y))
    samples += 1
    if retain_trace and i % 5 == 0:
      trace.append({'t':t, 'y':y, 'heading':heading, 'command':command, 'actual':actual})
  return {'valid':valid, 'samples':samples, 'rms_m':math.sqrt(squared/max(samples, 1)),
          'peak_m':peak, 'exit_peak_m':exit_peak, 'max_command_rate':max_rate,
          'saturated_steps':saturated, 'rate_limited_steps':limited,
          'reasons':dict(counts), 'trace':trace}


def grid():
  # +/-0.4 m deliberately violates U's assumed 0.2 m bound: not a passing test.
  for pair, direction, bias, error, delay, fault in itertools.product(
      ((12.0, 0.02), (18.0, 0.01)), (-1, 1), (0.0, 0.3), (-0.4, -0.2, 0.0, 0.2, 0.4),
      (0.1, 0.3), ('none', 'line_loss', 'stale', 'takeover')):
    yield Scenario(speed=pair[0], peak_curvature=pair[1], direction=direction, model_bias=bias,
                   differential_error=error, delay=delay, fault=fault)


def compare_pair(baseline, candidate):
  if not baseline['valid'] or not candidate['valid']:
    return {'valid_pair':False, 'regression':None, 'rms_improved':None}
  rms_delta = candidate['rms_m']-baseline['rms_m']
  peak_delta = candidate['peak_m']-baseline['peak_m']
  return {'valid_pair':True, 'rms_delta_m':rms_delta, 'peak_delta_m':peak_delta,
          'regression':rms_delta > 0.02 or peak_delta > 0.05,
          'rms_improved':rms_delta < -0.02}


def sweep():
  cases = []
  for scenario in grid():
    a, c = run(scenario, 'A'), run(scenario, 'C')
    for gain in (0.25, 0.5, 1.0):
      u = run(scenario, 'U', gain=gain)
      cases.append({'scenario':asdict(scenario), 'gain':gain,
                    'assumption_covered':abs(scenario.differential_error) <= scenario.assumed_error_bound,
                    'A':{k:v for k, v in a.items() if k != 'trace'},
                    'C':{k:v for k, v in c.items() if k != 'trace'},
                    'U':{k:v for k, v in u.items() if k != 'trace'},
                    'C_vs_A':compare_pair(a, c), 'U_vs_A':compare_pair(a, u)})
  summary = []
  for gain in (0.25, 0.5, 1.0):
    for covered in (True, False):
      rows = [r for r in cases if r['gain'] == gain and r['assumption_covered'] == covered]
      for arm in ('C', 'U'):
        comparisons = [r[arm+'_vs_A'] for r in rows]
        summary.append({'gain':gain, 'covered':covered, 'arm':arm, 'cases':len(rows),
                        'invalid_pairs':sum(not r['valid_pair'] for r in comparisons),
                        'regressions':sum(r['regression'] is True for r in comparisons),
                        'rms_improvements':sum(r['rms_improved'] is True for r in comparisons)})
  return {'schema':'synthetic-falsification-v2', 'source_commit':SOURCE_COMMIT,
          'deployment_approved':False, 'road_validation':False, 'neural_model_loaded':False,
          'scenario_count':len(list(grid())), 'gain_count':3,
          'regression_thresholds':{'rms_m':0.02, 'peak_m':0.05},
          'summary':summary, 'cases':cases}


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--output', type=Path, required=True)
  args = parser.parse_args()
  result = sweep()
  args.output.write_text(json.dumps(result, allow_nan=False))
  print(json.dumps({k:v for k, v in result.items() if k != 'cases'}, indent=2))


if __name__ == '__main__':
  main()
