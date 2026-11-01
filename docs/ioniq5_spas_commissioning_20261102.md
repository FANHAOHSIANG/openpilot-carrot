# Ioniq 5 CAN-FD: comma-only indicator commissioning

The existing `carrot-wip` implementation already supports the acknowledged SPAS
transport independently of a Mac/Jetson inference host. The older
`carrot-wip-map-hud` branch does not include that transport. This change adds a
commissioning CLI, not a new CAN controller, a Mac USB-CAN driver or an automatic
enablement. No model, steering, longitudinal, Panda or indicator policy is changed.

The available 2023 Ioniq 5 recording has both required bus-0 messages: 3,001
SPAS1/24 and 3,001 SPAS2/32 with valid CRC and advancing counters. Full-schema
replay through the new monitor sees 5,951 CAN events, 5,933 stock-ready samples
and 5,911 neutral/driver-ready samples. There are no captured diagnostic replies.
This establishes recorded preconditions, not live readiness, APRK handoff,
physical illumination, restoration or road validation. Other vehicles' prior
SPAS failures in `canfd_spas_blinkers_20261026.md` must not be attributed to this
2023 vehicle, and matching frames do not resolve those failure modes.

## Normal delivery

Pull/restart using the normal update flow on `FANHAOHSIANG/openpilot-carrot`,
branch `carrot-wip`. Do not overwrite a dirty vehicle checkout or transplant this
one script into the older map-HUD branch: it lacks the underlying transport.
Preserve local changes and confirm the installed branch before updating.
The SPAS implementation requires the matching normal Panda build. The CLI checks
live Panda's SPAS selection, but does not attest firmware signatures or replace
the normal boot/build checks. Mac Jetlink is not modified by this change.

## First step: read-only

With the vehicle stationary in Park and normal services running:

```sh
cd /data/openpilot
python -m tools.jetlink.spas_check
```

This command does not write Params or publish CAN. It observes exact ECAN frames,
CRC/counter continuity, neutral driver input, fresh Park/standstill/inactive
control state and at least three seconds of stable Panda health. Missing/stale,
future, unsupported or conflicting observations fail the preflight. Existing
SPAS selection is printed separately; a preflight pass does not enable it.

## Explicit stationary test

Only after reviewing a live preflight, select the existing
`CanfdBlinkerControl` / `CAN-FD SPAS indicators (trial)` setting in Carrot Web
and reboot normally. Keep `AutoBlinkerControl=0` and `CanfdBlinkerTest=0` for this
isolated commissioning test. Do not select direct/coexistence modes 3–18.
With ignition on, actual Park, zero speed, no active controls and pedals/stalk
released, run one direction:

```sh
python -m tools.jetlink.spas_check --test left
```

The CLI repeats preflight, verifies selected CarParams and live Panda SPAS flags,
then selects only the existing three-second acknowledged test 1 (left) or 2
(right). It does not publish raw CAN. It cancels on stale state, motion/control,
driver input, changed settings or CAN-health/rejection-count changes. A `finally`
block resets the test to zero after normal completion or exceptions. The existing
controller separately bounds the trial duration; process termination is not proof
of completed ECU restoration. No automatic retry or fallback is added.

The result separates ECU handoff ACKs, CAN-derived lamp feedback, and subsequent
restore ACK plus fresh neutral stock reception with stable health. Requested
commands and received feedback are not independent wire delivery or visual
confirmation. Observe the actual vehicle lamps. A failure or unconfirmed restore
must end this commissioning attempt; do not enable automation or repeat on the
other side to bypass it. Restore the trial option to OFF via normal settings and
reboot if the transport cannot be commissioned; confirm OEM stalk/parking
functions normally. Do not use direct modes to force a positive result.

A successful stationary left test does not certify right-side behavior, holding,
driver override, Mac inference co-load or any driving scenario. A right test is
separate, explicit and only appropriate after successful restoration/inspection.
Automatic operation remains unvalidated and is not enabled by this deliverable.

## Validation

The new monitor/CLI tests cover bad CRC, counter gaps, duplicate/future/stale
samples, bus selection, driver input, fresh parked control/health gates,
read-only default behavior, explicit left/right mode selection, automatic-mode
rejection and exception cleanup. Actual Params/native messaging in CLI lifecycle
tests are replaced with deterministic desktop adapters, not vehicle services.
Existing SPAS state-machine tests and recorded full-schema CAN replay supplement
these tests. Native device build, actual ECU handoff and physical lamp testing
remain pending on the user's C4.
