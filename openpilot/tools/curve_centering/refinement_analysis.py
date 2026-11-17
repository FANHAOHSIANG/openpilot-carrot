"""Compare offline refinement R with every retained original falsification case."""
import argparse
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path

from .simulation import Scenario, compare_pair, run


def analyze(original):
  rows = []
  for old in original['cases']:
    if old['gain'] != .25:
      continue
    scenario = Scenario(**old['scenario'])
    result = run(scenario, 'R')
    result.pop('trace')
    rows.append({'scenario': old['scenario'], 'covered': old['assumption_covered'],
                 'feasible': scenario.speed**2*scenario.peak_curvature <= scenario.authority_accel,
                 'A': old['A'], 'C': old['C'], 'U': old['U'], 'R': result,
                 'C_vs_A': old['C_vs_A'], 'R_vs_A': compare_pair(old['A'], result)})
  summaries = []
  for covered in (True, False):
    for feasible in (True, False):
      selected = [r for r in rows if r['covered'] == covered and r['feasible'] == feasible]
      summaries.append({'covered': covered, 'feasible': feasible, 'cases': len(selected),
                        'C_regressions': sum(r['C_vs_A']['regression'] is True for r in selected),
                        'R_regressions': sum(r['R_vs_A']['regression'] is True for r in selected),
                        'R_invalid': sum(not r['R']['valid'] for r in selected),
                        'R_exceedances': sum(not r['R']['within_assumed_lane'] for r in selected),
                        'R_new_exceedances_vs_A': sum(r['A']['within_assumed_lane'] and not r['R']['within_assumed_lane'] for r in selected)})
  regressions = [r for r in rows if r['covered'] and r['feasible'] and r['C_vs_A']['regression']]
  probes = []
  for old in regressions:
    scenario = Scenario(**old['scenario'])
    # Change only differential error, preserving plant, fault and thresholds.
    if scenario.model_bias == 0:
      corrected = replace(scenario, differential_error=0.)
      probes.append({'scenario': old['scenario'], 'intervention': 'zero_differential_error',
                     'comparison': compare_pair(run(corrected, 'A'), run(corrected, 'C'))})
  stale = Scenario(delay=.3, fault='stale')
  gain_bound_probes = []
  for fault in ('none', 'stale'):
    for gain in (.25, 1.):
      for bound in (0., .2):
        scenario = replace(stale, fault=fault, assumed_error_bound=bound)
        result = run(scenario, 'U', gain=gain)
        gain_bound_probes.append({'fault': fault, 'gain': gain, 'assumed_bound': bound,
                                  'comparison': compare_pair(run(scenario, 'A'), result)})
  return {'scope': 'offline_refinement_not_actuation_or_independent_validation', 'deployment_approved': False,
          'original_thresholds': original['regression_thresholds'], 'summary': summaries,
          'C_regression_groups': [{'model_bias': k[0], 'differential_error': k[1], 'count': v}
                                  for k, v in Counter((r['scenario']['model_bias'], r['scenario']['differential_error'])
                                                       for r in regressions).items()],
          'zero_error_probes': probes, 'gain_bound_fault_probes': gain_bound_probes, 'cases': rows}


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('original_sweep', type=Path)
  parser.add_argument('--output', type=Path, required=True)
  args = parser.parse_args()
  result = analyze(json.loads(args.original_sweep.read_text()))
  with args.output.open('x') as f:
    json.dump(result, f, allow_nan=False)
  print(json.dumps({k: v for k, v in result.items() if k != 'cases'}, indent=2))


if __name__ == '__main__':
  main()
