# controlsd publish plan-age crash — 2026-11-09

Recorded version: 32f9f3f74df63b0e0de9165a9f4d435f4f5f0d0e,
test/carrot-wip-upstream-20261104. Route 000003b3--7a06e99d02 segment 2.

At 20:25:54 Asia/Taipei, controlsd logs a Python traceback in Controls.publish:
`NameError: name 't_since_plan' is not defined`. The variable exists locally in
state_control, but is unavailable in publish. The crash is triggered once the
preceding longitudinalPlan/radarState all_checks becomes true; invalid inputs
short-circuit the expression and hide the bug. Manager reports exit code 1.
The segment briefly records 123 carControl and controlsState messages before
the crash. Segments 1/3/5/6 have no messages from these two services. Model and
pose stay near 20 Hz with valid pose inputs. The downstream invalid flags are
consistent with missing control input; this is separate from external inference
throughput and Xiaoge CPU overload. Missing manager heartbeats also occur;
this one-line patch does not establish their independent cause or resolution.

Fix: calculate t_since_plan locally in publish using the same frame/recv_frame
and DT_CTRL formula as state_control. Preserve all_checks and the inclusive
0..0.2 second plan/radar freshness gates. Do not force message validity.

Validation: execute the production publish method with mocked transport and
vehicle messages. Original fails six of seven cases with the recorded NameError;
patched passes seven. Verify fresh inputs, boundary, stale/future plan,
stale/future radar, invalid inputs, and continued publication of both messages.
Python compilation passes. No native/hardware integration or on-road validation
has been performed. The existing Xiaoge cooldown candidate is not included.

Run: python openpilot/selfdrive/controls/tests/test_publish_plan_age.py

Install/update the test branch only while parked, with a clean working tree;
record the previous branch/commit first. Do not use reset --hard. After reboot,
confirm the new commit and inspect new logs for uninterrupted carControl and
controlsState, valid downstream outputs, managerState heartbeat and no crash.
Do not engage assistance while communication alerts persist.
