"""Offline prototype for curve advisory release; not a vehicle-control input.

The reference cannot exceed the original target. Tightening is immediate.
The rate is an engineering trial for replay, NOT a validated vehicle setting.
"""
import math

CURVE_SOURCES = frozenset(('pre', 'route', 'vturn', 'atc', 'atc2'))


class SpeedRecoveryReference:
    def __init__(self, rise_kph_per_s=2.16):
        if not math.isfinite(rise_kph_per_s) or rise_kph_per_s <= 0:
            raise ValueError('invalid replay rate')
        self.rate = rise_kph_per_s
        self.reset()

    def reset(self):
        self.previous = None
        self.previous_time = None
        self.armed = False

    def update(self, *, now, raw, set_speed, ego, source, active, gas, brake):
        if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in (now, raw, set_speed, ego)) or not (0 <= ego <= 250 and 0 <= raw <= 250 and 0 <= set_speed <= 250):
            self.reset()
            return None
        target = min(raw, set_speed)
        valid = active is True and gas is False and brake is False and source in CURVE_SOURCES | {'road'}
        if not valid:
            self.reset()
            return target
        dt = now - self.previous_time if self.previous_time is not None else 0.0
        prior = self.previous
        if not 0 < dt <= 0.25:
            prior = None
            self.armed = False
        # Only smooth release of a previously binding curve advisory. No new lower limit.
        # A new tighter raw target always takes priority, including a changed setpoint.
        if prior is not None and self.armed and target > prior:
            result = min(target, max(ego, prior + self.rate * dt))
        else:
            result = target
        self.armed = (source in CURVE_SOURCES and raw < set_speed) or result < target
        self.previous, self.previous_time = result, now
        return result
