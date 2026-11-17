"""Disaggregate retained failure counts; never convert a baseline failure to a pass."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path

from .bridge_demo import demo_ticks
from .control_bridge import ControlBridge
from .simulation import Scenario, run


def analyze(sweep):
  rows = [r for r in sweep['cases'] if r['gain'] == .25 and r['assumption_covered']
          and r['scenario']['speed']**2*r['scenario']['peak_curvature'] <= r['scenario']['authority_accel']]
  arms = {}
  for arm in ('A', 'C', 'U'):
    bad = [r for r in rows if not r[arm]['within_assumed_lane']]
    comparisons = [r[arm+'_vs_A'] for r in rows] if arm != 'A' else []
    arms[arm] = {'exceedances': len(bad),
                 'threshold_regressions_vs_A': sum(c['regression'] is True for c in comparisons),
                 'invalid_pairs_vs_A': sum(not c['valid_pair'] for c in comparisons),
                 'new_exceedances_vs_A': sum(r['A']['within_assumed_lane'] for r in bad),
                 'peak_range_m': [min(r[arm]['peak_m'] for r in bad), max(r[arm]['peak_m'] for r in bad)],
                 'max_peak_delta_vs_A_m': max(r[arm]['peak_m']-r['A']['peak_m'] for r in rows),
                 'failure_groups': [{'delay': k[0], 'model_bias': k[1], 'fault': k[2], 'cases': v}
                                    for k, v in Counter((r['scenario']['delay'], r['scenario']['model_bias'],
                                                         r['scenario']['fault']) for r in bad).items()]}
  # Representative original failure and mechanistic interventions; do not tune a
  # production parameter or treat these probes as independent validation cases.
  probes = []
  original = Scenario(delay=.3, model_bias=.3, differential_error=0., fault='none')
  for name, scenario in [('original', original), ('zero_bias', Scenario(delay=.3, model_bias=0.)),
                         ('zero_transport_delay', Scenario(delay=0., model_bias=.3))]:
    for arm in ('A', 'C', 'U'):
      result = run(scenario, arm, gain=.25, retain_trace=True)
      trace = result.pop('trace')
      peak = max(trace, key=lambda r: abs(r['y']))
      probes.append({'probe': name, 'arm': arm, 'metrics': result, 'peak_sample': peak})
  bridge = ControlBridge('isolated')
  residuals = []
  prior = None
  reset_jerk = None
  for tick, observation, fault in demo_ticks():
    result = bridge.step(tick, observation)
    if result['injected_delta_curvature'] == 0 and abs(result['residual_curvature'] or 0.) > 1e-12:
      residuals.append({'t': tick.now_ns/1e9, 'fault': fault, 'state_difference': result['residual_curvature'],
                        'policy_difference': result['policy_delta_curvature'],
                        'lateral_accel_difference': result['residual_curvature']*tick.speed**2})
      if reset_jerk is None:
        reset_jerk = abs(result['baseline']['curvature']-prior['candidate']['curvature'])*tick.speed**2/.01
    prior = result
  decay_ratios = [b['state_difference']/a['state_difference'] for a, b in zip(residuals, residuals[1:], strict=False)]
  return {'scope': 'synthetic_failure_attribution_not_road_validation', 'deployment_approved': False,
          'feasible_covered_cases': len(rows), 'arms': arms, 'representative_probes': probes,
          'withdrawal': {'residual_ticks_at_original_1e_12_reporting_threshold': len(residuals),
                         'nonzero_same_state_policy_differences': sum(r['policy_difference'] != 0 for r in residuals),
                         'first': residuals[0], 'last': residuals[-1],
                         'expected_ratio_from_existing_0_1s_filter': math.exp(-.01/.1),
                         'max_ratio_error': max(abs(r-math.exp(-.01/.1)) for r in decay_ratios),
                         'hypothetical_direct_reset_jerk_mps3': reset_jerk,
                         'existing_rate_limit_mps3': 5.,
                         'interpretation': 'historical state persists; no new policy injection after withdrawal; physical handover unknown'}}


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('sweep', type=Path)
  parser.add_argument('--output', type=Path, required=True)
  args = parser.parse_args()
  result = analyze(json.loads(args.sweep.read_text()))
  with args.output.open('x') as f:
    json.dump(result, f, indent=2, allow_nan=False)
  print(json.dumps({'arms': result['arms'], 'withdrawal': result['withdrawal']}, indent=2))


if __name__ == '__main__':
  main()
