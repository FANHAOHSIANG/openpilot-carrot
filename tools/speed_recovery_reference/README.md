# Speed recovery reference v1

Offline candidate, not imported by the vehicle planner. Never install as a control setting.
Initial engineering rate 2.16 km/h/s (0.6 m/s²), not a validated tuning value.
Never raises the original target or delays a lower target; reset on driver intervention, invalid or interrupted inputs.
Historical open-loop trace 2026-11-10, segments 15–18: 2,262 rows, 508 changed reference samples, upward target jumps >=10 km/h 5 -> 0, downward 6 -> 6. Compare adjacent rows less than 0.2s apart with both rows longActive and no gas/brake. Actual vehicle response is not simulated. No ramp confirmation or validation of acceleration, braking, or jerk. Do not infer vehicle safety from these counts.
Run python -m unittest in this directory.
