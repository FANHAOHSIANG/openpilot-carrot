"""Offline comparison only. Never import from a vehicle control process.

CSV columns: t_s,speed_kph,steer_deg,torque,desired_curvature.
Each CSV must describe the same independently identified replay scenario.
Use --compare to include a separately generated candidate trace.
The flag is an offline report switch, NOT a vehicle setting.
No controller, Params, CAN, or safety interfaces are accessed.
"""
import argparse
import csv
import json
import math
from pathlib import Path


FIELDS = ("t_s", "speed_kph", "steer_deg", "torque", "desired_curvature")


def read_trace(path):
  with Path(path).open(newline="") as f:
    reader = csv.DictReader(f)
    if not set(FIELDS).issubset(reader.fieldnames or []):
      raise ValueError("missing required trace columns")
    rows = [tuple(float(row[k]) for k in FIELDS) for row in reader]
  if len(rows) < 2 or any(not math.isfinite(v) for row in rows for v in row):
    raise ValueError("insufficient or non-finite trace")
  if any(b[0] <= a[0] for a, b in zip(rows, rows[1:])):
    raise ValueError("timestamps must be strictly increasing")
  return rows


def summarize(rows, max_speed, max_gap, deadband):
  # Never count a reversal across an excluded sample or missing interval.
  intervals = []
  current = []
  for row in rows:
    if row[1] < 0 or row[1] > max_speed:
      if current:
        intervals.append(current)
        current = []
      continue
    if current and row[0] - current[-1][0] > max_gap:
      intervals.append(current)
      current = []
    current.append(row)
  if current:
    intervals.append(current)
  duration = 0.0
  travel = 0.0
  reversals = 0
  peak_to_peak = 0.0
  curvature_travel = 0.0
  for segment in intervals:
    if len(segment) < 2:
      continue
    duration += segment[-1][0] - segment[0][0]
    angles = [row[2] for row in segment]
    peak_to_peak = max(peak_to_peak, max(angles) - min(angles))
    travel += sum(abs(b[2] - a[2]) for a, b in zip(segment, segment[1:]))
    curvature_travel += sum(abs(b[4] - a[4]) for a, b in zip(segment, segment[1:]))
    previous = 0
    for row in segment:
      sign = 1 if row[3] > deadband else -1 if row[3] < -deadband else 0
      if sign:
        reversals += int(previous != 0 and sign != previous)
        previous = sign
  if duration <= 0:
    raise ValueError("no contiguous low-speed coverage")
  return {
    "duration_s": duration,
    "steering_peak_to_peak_deg": peak_to_peak,
    "steering_travel_deg_per_s": travel / duration,
    "torque_reversals_per_s": reversals / duration,
    "curvature_variation_per_s": curvature_travel / duration,
  }


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("baseline")
  parser.add_argument("--compare", metavar="CANDIDATE_CSV")
  parser.add_argument("--max-speed", type=float, required=True, help="analysis window in km/h")
  parser.add_argument("--max-gap", type=float, required=True, help="maximum contiguous sample gap in seconds")
  parser.add_argument("--torque-deadband", type=float, required=True, help="measurement noise exclusion in trace units")
  args = parser.parse_args()
  config = (args.max_speed, args.max_gap, args.torque_deadband)
  if not all(math.isfinite(v) for v in config) or min(config) < 0 or args.max_gap == 0:
    parser.error("invalid analysis configuration")
  baseline = read_trace(args.baseline)
  report = {"baseline": summarize(baseline, *config), "deployment_approved": False}
  if args.compare:
    candidate = read_trace(args.compare)
    # Require identical timeline and eligible speed mask; do not silently pair different runs.
    if len(baseline) != len(candidate) or any(
      abs(a[0] - b[0]) > 1e-6 or (0 <= a[1] <= args.max_speed) != (0 <= b[1] <= args.max_speed)
      for a, b in zip(baseline, candidate)
    ):
      raise ValueError("candidate timeline or low-speed coverage differs")
    report["candidate"] = summarize(candidate, *config)
  report["warning"] = "Descriptive metrics only; reduced motion does not establish safe lane keeping or turn response."
  print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
  main()
