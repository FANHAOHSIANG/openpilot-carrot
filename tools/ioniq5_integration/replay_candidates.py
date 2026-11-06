"""Desktop-only HCOP curve replay and HKG event simulation."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from hcop_curve_v2 import CurveV2
from hkg_state import AccStateMachine, DT_CTRL, ET, EventNameSP, INTERP_SPEEDS, KP_INTERP, MadsStateMachine

MAX_AGE_NS = 250_000_000
MODEL_GAP_NS = 150_000_000


class Events:
  def __init__(self, kinds=(), names=()):
    self.kinds = kinds
    self.names = names

  def contains(self, kind):
    return kind in self.kinds

  def has(self, name):
    return name in self.names

  def contains_in_list(self, names):
    return any(self.has(name) for name in names)


def simulate_events():
  """Feed labeled synthetic events into the pinned HKG transitions."""
  scenarios = {}
  for name, sequence in {
    "cancel_and_release": [
      ("enable", (ET.ENABLE,), (), ()),
      ("cancel", (ET.USER_DISABLE,), (), ()),
      ("release_without_enable", (), (), ()),
      ("explicit_enable", (ET.ENABLE,), (), ()),
    ],
    "steering_pause_and_reenable": [
      ("enable", (ET.ENABLE,), (), ()),
      ("pause_lateral", (), (ET.USER_DISABLE,), (EventNameSP.silentLkasDisable,)),
      ("release_without_enable", (), (), ()),
      ("explicit_lateral_enable", (), (ET.ENABLE,), ()),
      ("fault", (ET.IMMEDIATE_DISABLE,), (), ()),
    ],
  }.items():
    acc = AccStateMachine()
    sd = SimpleNamespace(enabled=False, state_machine=acc, events=Events(), events_sp=Events())
    mads = MadsStateMachine(SimpleNamespace(selfdrive=sd))
    rows = []
    for label, stock, extension, names in sequence:
      sd.events.kinds = stock
      sd.events_sp.kinds, sd.events_sp.names = extension, names
      sd.enabled, acc_active = acc.update(sd.events)
      mads_enabled, mads_active = mads.update()
      rows.append({"event": label, "acc_state": acc.state, "acc_active": acc_active,
                   "mads_state": mads.state, "mads_enabled": mads_enabled, "mads_active": mads_active})
    scenarios[name] = rows
  return scenarios


def summarize(values):
  if not values:
    return {"frames": 0}
  return {"frames": len(values), "min": min(values), "median": float(np.median(values)), "max": max(values)}


def replay(path, schema_dir):
  # Use the recording's complete cereal schema. No messaging sockets are opened.
  import capnp
  import zstandard

  schema_dir = schema_dir.resolve()
  schema = capnp.load(str(schema_dir / "log.capnp"), imports=[str(schema_dir)])
  curve = CurveV2()
  latest = {}
  model_stamp = None
  skip_until = 0
  counts = Counter()
  caps, gains = [], []
  with path.open("rb") as stream, zstandard.ZstdDecompressor().stream_reader(stream) as reader:
    raw = reader.read()
  for event in schema.Event.read_multiple_bytes(raw, traversal_limit_in_words=2**30):
    name = event.which()
    stamp = event.logMonoTime
    if name in ("carState", "carControl", "controlsState", "longitudinalPlan"):
      if name not in latest or stamp >= latest[name].logMonoTime:
        latest[name] = event
      continue
    if name != "modelV2":
      continue
    counts["model_frames"] += 1
    if model_stamp is not None and stamp <= model_stamp:
      counts["duplicate_or_out_of_order"] += 1
      continue
    if model_stamp is None or stamp - model_stamp > MODEL_GAP_NS:
      curve = CurveV2()
      skip_until = 0
    model_stamp = stamp

    def fresh(service):
      value = latest.get(service)
      return value is not None and value.valid and 0 <= stamp - value.logMonoTime <= MAX_AGE_NS

    if not event.valid or not all(fresh(key) for key in ("carState", "carControl", "controlsState")):
      counts["invalid_or_stale"] += 1
      curve.reset()
      continue
    cs, cc = latest["carState"].carState, latest["carControl"].carControl
    speed = float(cs.vEgo)
    if cc.latActive and 0 < speed < 30 / 3.6:
      gains.append(float(np.interp(speed, INTERP_SPEEDS, KP_INTERP)))
    model = event.modelV2
    if str(model.meta.laneChangeState) in ("laneChangeStarting", "laneChangeFinishing"):
      skip_until = stamp + 2_000_000_000
    if not cc.longActive or cs.gasPressed or cs.brakePressed or stamp < skip_until:
      counts["inactive_or_driver_override"] += 1
      curve.reset()
      continue
    curvature = float(latest["controlsState"].controlsState.curvature)
    x, v, yaw = (np.asarray(field, dtype=float) for field in (model.position.x, model.velocity.x, model.orientationRate.z))
    if (not math.isfinite(speed) or speed < 0 or not math.isfinite(curvature)
        or any(a.shape != (33,) or not np.isfinite(a).all() for a in (x, v, yaw))):
      counts["invalid_inputs"] += 1
      curve.reset()
      continue
    cap = curve.update(x, yaw / np.maximum(v, 1.0), v, speed, speed**2 * abs(curvature), curvature)
    counts["curve_evaluated"] += 1
    if math.isfinite(cap):
      caps.append(cap)
      counts["curve_negative_cap"] += int(cap < 0)
      if fresh("longitudinalPlan"):
        target = float(latest["longitudinalPlan"].longitudinalPlan.aTarget)
        if math.isfinite(target):
          counts["curve_below_recorded_accel_by_0_1"] += int(cap < target - 0.1)
  return {"counts": dict(counts), "hcop_finite_accel_cap_mps2": summarize(caps),
          "hkg_nominal_kp_below_30_kph": summarize(gains)}


def main():
  ap = argparse.ArgumentParser(description=__doc__)
  ap.add_argument("--rlog", type=Path)
  ap.add_argument("--schema-dir", type=Path, help="Directory with the recording's log.capnp and its imports")
  args = ap.parse_args()
  if Path("/AGNOS").exists() or Path("/TICI").exists():
    ap.error("Run this tool on a computer.")
  if bool(args.rlog) != bool(args.schema_dir):
    ap.error("--rlog and --schema-dir must be supplied together")
  result = {"hkg_synthetic_events": simulate_events(), "synthetic_tick_seconds": DT_CTRL}
  if args.rlog:
    result["recorded_inputs"] = replay(args.rlog, args.schema_dir)
  print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
  main()
