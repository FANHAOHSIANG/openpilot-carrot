"""Passive low-speed oscillation research observer. Never publishes control messages."""
import math
import os
import time

KEY = "LowSpeedOscillationShadow"
EVENT = "lowSpeedOscillationShadow"
SERVICES = ("modelV2", "carState", "carControl", "controlsState", "carOutput", "liveParameters")


class Shadow:
  """Same medium-strength model-only candidate as the offline 11/28 experiment."""
  def __init__(self):
    self.reset()

  def reset(self):
    self.last = None
    self.value = None

  def sample(self, t, raw, reason):
    if not math.isfinite(t) or not math.isfinite(raw):
      self.reset()
      return None, "nonfinite"
    if reason:
      self.reset()
      return raw, reason
    prev, last = self.value, self.last
    self.value, self.last = raw, t
    if prev is None:
      return raw, "initial"
    dt = t - last
    if not 0 < dt <= .075:
      return raw, "gap"
    if abs(raw - prev) > .004:
      return raw, "large_change"
    self.value = prev + -math.expm1(-dt / .1) * (raw - prev)
    return self.value, "shadow_applied"


def finite(value):
  try:
    value = float(value)
    return value if math.isfinite(value) else None
  except (TypeError, ValueError, OverflowError):
    return None


def main():
  # Deliberately isolated from controlsd, with no actuator or CAN publisher.
  from openpilot.cereal import messaging
  from openpilot.common.params import Params
  from openpilot.common.swaglog import cloudlog

  try:
    os.nice(10)
  except OSError:
    pass
  params = Params()
  if not params.get_bool(KEY):
    return
  sm = messaging.SubMaster(list(SERVICES), poll="modelV2")
  shadow = Shadow()
  last_log = 0.
  last_reason = None
  last_param = 0.
  cloudlog.event(EVENT + "Start", version=1, mode="observe_only", tau_s=.1, max_gap_s=.075,
                 max_step=.004, speed_range_mps=[1, 5], deployment_approved=False)
  while True:
    sm.update(100)
    now = time.monotonic()
    if now - last_param >= .5:
      last_param = now
      if not params.get_bool(KEY):
        return
    if not sm.updated["modelV2"]:
      if now - sm.recv_time["modelV2"] > .25:
        shadow.reset()
      continue
    try:
      md, cs, cc = sm["modelV2"], sm["carState"], sm["carControl"]
      st, co, lp = sm["controlsState"], sm["carOutput"], sm["liveParameters"]
      model_ns = int(sm.logMonoTime["modelV2"])
      raw = float(md.action.desiredCurvature)
      speed = float(cs.vEgo)
      age = {k: now - sm.recv_time[k] for k in SERVICES}
      valid = all(sm.all_checks([k]) and 0 <= age[k] <= .25
                  for k in ("modelV2", "carState", "carControl", "controlsState"))
      yaw = list(md.orientation.z[:17])
      turn = (len(yaw) < 17 or not all(math.isfinite(x) for x in yaw) or
              max(abs(x) for x in yaw) > .10 or str(md.meta.laneChangeState) != "off" or
              cs.leftBlinker or cs.rightBlinker)
      reason = ""
      if not valid or not cs.canValid or cs.canTimeout or not 0 <= md.frameDropPerc <= .01:
        reason = "invalid_or_stale"
      elif not cc.latActive or cs.standstill or str(cs.gearShifter) != "drive":
        reason = "inactive"
      elif cs.steeringPressed or cs.steerFaultTemporary or cs.steerFaultPermanent:
        reason = "driver_or_fault"
      elif not math.isfinite(speed) or not 1 <= speed <= 5:
        reason = "speed"
      elif turn:
        reason = "turn_proxy"
      elif not math.isfinite(raw) or abs(raw) > .02:
        reason = "curvature_range"
      value, outcome = shadow.sample(model_ns / 1e9, raw, reason)
      # Full-rate original controls are already present in rlog. Shadow report
      # is rate-limited to 5 Hz during low speed; transitions also sampled.
      if now - last_log < .2 or (not 0 <= speed <= 5 and last_reason == outcome):
        continue
      last_log, last_reason = now, outcome
      state = st.lateralControlState
      pid = {}
      if state.which() == "torqueState":
        ts = state.torqueState
        pid = {k: finite(getattr(ts, k)) for k in ("p", "i", "d", "f", "error", "output")}
        pid["saturated"] = bool(ts.saturated)
      output_valid = sm.all_checks(["carOutput"]) and 0 <= age["carOutput"] <= .25
      live_valid = sm.all_checks(["liveParameters"]) and 0 <= age["liveParameters"] <= .25
      cloudlog.event(EVENT, version=1, mode="observe_only", model_ns=model_ns,
                     frame_id=int(md.frameId), valid=bool(valid), reason=outcome,
                     source_ns={k: int(sm.logMonoTime[k]) for k in SERVICES},
                     speed_mps=finite(speed), raw_curvature=finite(raw), shadow_curvature=value,
                     commanded_curvature=finite(cc.actuators.curvature),
                     steering_deg=finite(cs.steeringAngleDeg), steering_rate=finite(cs.steeringRateDeg),
                     driver_pressed=bool(cs.steeringPressed), lat_active=bool(cc.latActive),
                     driver_torque=finite(cs.steeringTorque), eps_torque=finite(cs.steeringTorqueEps),
                     command_torque=finite(cc.actuators.torque),
                     applied_torque=finite(co.actuatorsOutput.torque) if output_valid else None,
                     steer_ratio=finite(lp.steerRatio) if live_valid else None,
                     pid=pid, lane_y0=[finite(line.y[0]) if len(line.y) else None for line in md.laneLines],
                     lane_probs=[finite(p) for p in md.laneLineProbs],
                     deployment_approved=False)
    except (AttributeError, ValueError, TypeError, OverflowError, IndexError, RuntimeError) as e:
      shadow.reset()
      if now - last_log >= 1.:
        last_log = now
        cloudlog.event(EVENT + "Skipped", reason=type(e).__name__, deployment_approved=False)


if __name__ == "__main__":
  main()
