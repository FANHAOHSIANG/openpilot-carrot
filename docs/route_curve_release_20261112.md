# Confirmed route-curve release

Based on `test/truck-clearance-204f9cca` at `200b0c21d2a4076dd17927533ca2ec80e32b8f00`.

The route/OSM ceiling previously recovered at at most 3.6 km/h/s even with valid
matched geometry. Vision could release sooner while the selected route ceiling
still held the longitudinal target down. The route now requires at least three
fresh matched frames spanning 0.2 seconds in a 0.25-second window, then releases
at at most 7.2 km/h/s, never above the lowest candidate in that window. Tightening
still applies immediately. Route replacement, unconfirmed/repeated input and
missing geometry clear the fast-release evidence. Missing data retains the prior
0.35-second hold and 3.6 km/h/s fallback.

This changes a speed ceiling, not commanded acceleration. The existing source
minimum, driver override, control activation, lead and cruise limits, and
turn_accel/MPC acceleration and jerk controls remain in place. Henry's separate
curve controller and turn_slow are not installed alongside them. Junction intent
from turn_ahead remains separate future work; it needs reliable road-graph and
ATC integration rather than another independent braking controller.

## Offline validation

- 140 tests across route geometry, actual CarrotMan/CarrotServ method integration,
  OSM matching, visual curve speed and turn-acceleration limits.
- 25 Wiki generator tests; modified KO/EN manual-region patch applied to generated
  pages and validated; user-documentation mapping check passed.
- Focused Ruff, compilation and git diff whitespace checks.
- Repaired two pre-existing Ruff failures in OSM code/tests. Updated the existing
  planner-test fixture with its missing coasting timer and timestep fields;
  production longitudinal-planner behavior is unchanged.

A synthetic A/B using the same road/start=40 fixture and subsequent confirmed
straight replacement starts at a 47.11 km/h ceiling. At two seconds the old/new
ceilings are 53.41/58.27 km/h. Time to an 80 km/h ceiling is 9.40/5.05 seconds,
including route reacquisition. These are ceiling calculations with prescribed
inputs, not a closed-loop vehicle simulation, log replay, or measured acceleration.
No C4 installation or vehicle test was performed.
