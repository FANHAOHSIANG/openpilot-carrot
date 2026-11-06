"""Offline extraction of HCOP CurveV2 (henryopen/openpilot 1283b4d3).
Original algorithm and constants. Standalone units and model timestep.
Copyright (c) 2018, Comma.ai, Inc., and HCOP contributors. MIT, see repository LICENSE.
"""
import numpy as np

DT_MDL = 0.05

V_FLOOR = 15 * (1.0 / 3.6)  # ...but once slowing, this is as far down as it goes
_V2_T_IDX = np.array([10.0 * (i / 32) ** 2 for i in range(33)])   # ModelConstants.T_IDXS
_V2_LAT_BP = [10., 20., 40., 60., 80., 100.]  # km/h
_V2_LAT_V = [1.3, 1.5, 1.8, 1.7, 1.5, 1.3]   # m/s^2, felt (actual) lateral acceleration
_V2_K_CAL = 1.15            # plan curvature read this way vs driven, set so the apex lands on the comfort curve
_V2_J_MAX = 0.8             # m/s^3, how fast this car winds into a corner
_V2_J_PLAN_TO_DEMAND = 1 / 0.68   # the plan's own lateral jerk vs what the controller asks on arrival (median)
_V2_A_START = 1.0           # m/s^2 of needed deceleration before braking at all: late and firm, not long and light
_V2_A_STOP = 0.3            # braking, let go once less than this is needed
_V2_A_MAX = 1.6             # m/s^2, the most an ordinary driver uses for a corner
_V2_D_MARGIN_T = 0.8        # s: be down to speed this far before the point
_V2_A_TOTAL = 2.0           # m/s^2, longitudinal and lateral together on the way out
_V2_SLOW_TURN_V = 40 * (1.0 / 3.6)   # below this, hold through the whole turn, not just to the apex (25 until
_V2_REQ_TAU_UP = 0.6        # s: the needed deceleration jumps up with the model frame - smooth that
_V2_REQ_TAU_DOWN = 0.15     # s: but let go quickly once it has been done
_V2_START_HOLD = 0.3        # s over _V2_A_START before braking
_V2_MIN_BRAKE = 1.0         # s: once braking, no acceleration for at least this long
_V2_JERK_T_MIN = 1.0        # s
_V2_ONSET_J = 1.5           # m/s^3; 0 turns the ramp off
_V2_A_START_RAMP = 0.6      # m/s^2 of needed deceleration before braking, with the ramp on
_FAR_T_BP = [3., 4., 5., 6., 7., 8.]      # s, time of the plan point
_FAR_GAIN = [1., 1.15, 1.25, 1.45, 1.6, 1.8]
_FAR_LIFT = 0.1           # m/s^2 of needed deceleration: stop gaining speed
_FAR_START = 0.3          # m/s^2: and past this, slow gently
_FAR_A_MAX = 0.5          # m/s^2
_V2_A_MAX_ANT = 2.0       # m/s^2, near-field braking with anticipation on (was _V2_A_MAX)
_WIND_LAT = 1.0      # m/s^2, a real bend
_WIND_MIN_T = 0.5    # s above it
_WIND_END = 0.3      # m/s^2, the bend is over
_WIND_WIN = 25.      # s: the bend before has to have ended this recently
_WIND_HOLD = 12.     # s after the bend
_WIND_A = 0.3        # m/s^2
_WIND_DV = 5 * (1.0 / 3.6)


class CurveV2:
  def __init__(self):
    self.anticipate = True
    # winding road: kept across reset() (a press of the accelerator between bends does not forget them)
    self.wind_t = 0.
    self.wind_in = 0.
    self.wind_pk = 0.
    self.wind_v_pk = 0.
    self.wind_v_ref = 0.
    self.wind_ends: list[float] = []
    self.reset()

  def reset(self) -> None:
    self.braking = False
    self.req_f = 0.
    self.over_t = 0.
    self.brake_t = 0.
    self.v_target = 0.
    self.a_cmd = 0.

  def update(self, x, k, vp, v_ego: float, lat_now: float, k_now: float) -> float:
    """x/k/vp: the plan's distance ahead, curvature and speed at each of its 33 points.
    Returns a ceiling on the longitudinal acceleration, np.inf where the corner has nothing to say."""
    kk = np.abs(k)
    ks = np.concatenate([kk[:1], (kk[:-2] + kk[1:-1] + kk[2:]) / 3, kk[-1:]]) / _V2_K_CAL
    kc = np.maximum(ks, 1e-4)
    # speed the comfort curve allows at each point; the allowance depends on the speed, so iterate
    vv = np.sqrt(np.interp(v_ego * 3.6, _V2_LAT_BP, _V2_LAT_V) / kc)
    for _ in range(2):
      vv = np.sqrt(np.interp(vv * 3.6, _V2_LAT_BP, _V2_LAT_V) / kc)
    v_lat = np.where(ks > 1e-4, vv, 99.)
    # speed the steering allows: the plan's lateral jerk where it is actually winding into a corner
    # (lateral >= 0.4 and rising, from _V2_JERK_T_MIN - see there), scaled to what will be asked on
    # arrival, and that falls with v^3
    alp = vp ** 2 * kk
    dj = np.zeros(33)
    dj[1:] = np.abs(np.diff(alp)) / np.maximum(np.diff(_V2_T_IDX), 0.05)
    rising = np.zeros(33, dtype=bool)
    rising[1:] = alp[1:] > alp[:-1]
    dj[~((alp >= 0.4) & rising & (_V2_T_IDX >= _V2_JERK_T_MIN))] = 0.
    j_dem = dj * _V2_J_PLAN_TO_DEMAND
    v_jerk = np.where(j_dem > 0.05, np.maximum(vp, 1.) * (_V2_J_MAX / np.maximum(j_dem, 1e-6)) ** (1 / 3), 99.)
    v_allow = np.maximum(np.minimum(v_lat, v_jerk), V_FLOOR)
    # the deceleration it takes to be down to that by each point
    d = np.maximum(x - _V2_D_MARGIN_T * v_ego, 0.5 * x)
    need = (v_ego ** 2 - v_allow ** 2) / (2 * np.maximum(d, 2.))
    if _V2_ONSET_J > 0.:
      # building up to a deceleration D at _V2_ONSET_J takes D / J seconds at half of it on average, which
      # costs about v * D / 2J of the distance - so ask as if that much less road were left
      t_ramp = np.clip(need, 0., _V2_A_MAX_ANT if self.anticipate else _V2_A_MAX) / _V2_ONSET_J
      need = (v_ego ** 2 - v_allow ** 2) / (2 * np.maximum(d - v_ego * t_ramp / 2., 2.))
    need[x < 2.] = 0.
    a_raw = float(need.max())
    tau = _V2_REQ_TAU_UP if a_raw > self.req_f else _V2_REQ_TAU_DOWN
    self.req_f += (a_raw - self.req_f) * min(DT_MDL / tau, 1.)
    a_req = max(self.req_f, 0.)
    ahead_pts = x > 0.5
    self.v_target = float(v_allow[ahead_pts].min()) if ahead_pts.any() else 99.
    # still tightening: sharper within the next 2 s than where we are now
    near = (_V2_T_IDX > 0.2) & (_V2_T_IDX <= 2.0)
    tightening = ks[near].max() > abs(k_now) * 1.05 and ks[near].max() > 0.004

    if self.braking:
      self.brake_t += DT_MDL
      self.braking = a_req > _V2_A_STOP or self.brake_t < _V2_MIN_BRAKE
    else:
      a_start = _V2_A_START_RAMP if _V2_ONSET_J > 0. else _V2_A_START
      self.over_t = self.over_t + DT_MDL if a_req >= a_start else 0.
      self.braking = self.over_t >= _V2_START_HOLD
      self.brake_t = 0.
      self.a_cmd = 0.

    if self.braking:
      target = min(a_req, _V2_A_MAX_ANT if self.anticipate else _V2_A_MAX)
      # deepen at most at _V2_ONSET_J; easing off is not held back
      self.a_cmd = min(target, self.a_cmd + _V2_ONSET_J * DT_MDL) if _V2_ONSET_J > 0. else target
      a = -self.a_cmd
    elif a_req > 0.25:
      a = 0.                     # a corner is coming that will need braking: stop gaining speed
    elif lat_now > 0.6 and (tightening or v_ego < _V2_SLOW_TURN_V):
      a = 0.                     # in the corner, apex still ahead: hold
    elif lat_now > 0.3:
      a = float(np.sqrt(max(_V2_A_TOTAL ** 2 - lat_now ** 2, 0.)))   # past the apex: out inside the g-g circle
    else:
      a = np.inf
    a = min(a, self._winding(v_ego, lat_now))
    if self.anticipate:
      a = min(a, self._far(x, ks, v_ego))
    if v_ego <= V_FLOOR and a < 0.:
      a = 0.
    return a

  def _winding(self, v_ego: float, lat_now: float) -> float:
    """After the second real bend in a row, a slow pick-up to just over that bend's apex speed (see _WIND_*)."""
    self.wind_t += DT_MDL
    if lat_now > _WIND_LAT:
      self.wind_in += DT_MDL
      if lat_now >= self.wind_pk:
        self.wind_pk, self.wind_v_pk = lat_now, v_ego
    elif lat_now < _WIND_END:
      if self.wind_in >= _WIND_MIN_T:
        self.wind_ends = [e for e in self.wind_ends if self.wind_t - e < _WIND_WIN] + [self.wind_t]
        self.wind_v_ref = self.wind_v_pk
      self.wind_in, self.wind_pk = 0., 0.
    if len(self.wind_ends) >= 2 and self.wind_t - self.wind_ends[-1] < _WIND_HOLD and lat_now < _WIND_LAT:
      return _WIND_A if v_ego < self.wind_v_ref + _WIND_DV else 0.
    return np.inf

  @staticmethod
  def _far(x, ks, v_ego: float) -> float:
    """From _FAR_T_BP[0] out: the corner taken as sharper than it looks, and only a lift or a light brake for it."""
    far = (_V2_T_IDX >= _FAR_T_BP[0]) & (ks > 1e-4)
    if not far.any():
      return np.inf
    kc = ks[far] * np.interp(_V2_T_IDX[far], _FAR_T_BP, _FAR_GAIN)
    vv = np.sqrt(np.interp(v_ego * 3.6, _V2_LAT_BP, _V2_LAT_V) / kc)
    for _ in range(2):
      vv = np.sqrt(np.interp(vv * 3.6, _V2_LAT_BP, _V2_LAT_V) / kc)
    vv = np.maximum(vv, V_FLOOR)
    d = np.maximum(x[far] - _V2_D_MARGIN_T * v_ego, 0.5 * x[far])
    need = float(((v_ego ** 2 - vv ** 2) / (2 * np.maximum(d, 2.))).max())
    if need > _FAR_START:
      return -min(need, _FAR_A_MAX)
    if need > _FAR_LIFT:
      return 0.
    return np.inf
