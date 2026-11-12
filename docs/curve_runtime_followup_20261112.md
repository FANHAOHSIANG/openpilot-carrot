# Manual cruise ceiling and auxiliary runtime follow-up

Scope: `test/truck-clearance-204f9cca`, based on `a2ec4d8e`.

A recorded drive showed the selected cruise speed rising in 5 km/h steps with
AutoSpeedUptoRoadSpeedLimit=100. This branch now caps automatic road/model
updates at their incoming selected speed, including the early model-only return
and road-limit synchronization. Automatic road updates cannot overwrite the
saved brake/resume speed. Explicit SPEED UP and physical speed buttons retain
manual adjustment. Existing pedal synchronization remains independently configured;
it was disabled in the analyzed drive. No vehicle parameters were written.

Jetlink preparation now needs a fresh host telemetry reply, matching loaded model
when reported, and valid recent device memory data below 85%. A daemon heartbeat
alone is insufficient. Memory pressure cancels a pending preparation; failure
blocks retries while readiness remains asserted. A lost-ready/reconnected peer
can rearm preparation. Internal inference continues. This does not establish why
the previous drive reported ready while the owner was not using Jetlink.

OSM work retains low scheduler priority and the original one-second result expiry.
The ordinary work interval is bounded to 0.2–0.4 s, targeting 20% of one CPU rather
than sleeping up to the entire expiry window. Long tile loads can still expire;
no stale geometry is relabeled fresh. Road-load optimization and device profiling
remain possible follow-ups.

The observed commIssue reports identified invalid driverMonitoringState and
longitudinalPlan, not a stopped process. Their upstream check failures now have
rate-limited diagnostic records. Selfdrived records sample/evaluate/publish timing
and scheduler wait. No alert, input-validity requirement, or soft-disable behavior
was removed. The root cause of those invalid inputs and control-loop delays is
not yet proven; these warnings are not claimed fixed by this patch.

Validation:

- 141 curve/OSM/selection/turn-acceleration tests.
- 156 cruise-button and ceiling tests through the repository offline runner
  (real schemas and production cruise code; settings isolated and live IPC blocked).
- 48 Jetlink readiness/preparation/resource and runtime-diagnostic tests.
- 25 Wiki generator/validator tests; nine staged manual regions validated.
- Changed-path lint, Python syntax and documentation checks.
- Segment 15 policy-input comparison: 1,524 recorded frames with selection 50,
  no gas and no button; 771 old-policy increase candidates were capped at 50.
  This assumes automatic increase unpaused, uses recorded lead/road inputs, and
  is not closed-loop replay or proof of actual vehicle acceleration.

Installation requires the user to pull and fully restart while parked. New drive
logs must verify OSM freshness, memory usage, cruise selection and warning timing.
The upstream Wiki was not changed for this test-branch-only policy.
