# v0.1 validation — 2026-11-16

Base: `0e462225e4184df0ee4e8cfda7b4cc7f69fbbf38`, branch
`test/carrot-wip-upstream-20261104`. Implementation is isolated to a new tools
package and its focused CI workflow. No changes to controlsd, the planners,
manager, Params, cereal, CAN safety, vehicle firmware or existing model artifacts.

## Local evidence

- 26 focused Python tests using the repository's pycapnp 2.1.0: both bend directions and signed inner bias; raw versus
  requested path; explicit camera/body calibration; independent lane x grids;
  exact partial-horizon endpoints; no extrapolation; invalid/non-monotonic/crossed geometry; exact model-time join;
  stale and future data; invalid messages; manual intervention; lane-change
  recovery; geometry jumps; time gaps; no diagnosis during warmup; bounded live
  history; read-only HTTP methods; full cereal encoding/decoding; corrupt input;
  episode boundaries; and safe embedded JSON.
- Repository Ruff configuration and whitespace checks pass.
- Six complete user-provided local logs: 7,060 lateralPlan frames, 3,499 admitted
  after the observer's filters. A seventh file fails full cereal parsing and is
  rejected in full. No silently accepted truncated tail.
- Admitted frames: 771 classified left, 182 right and 2,546 straight. These are
  frame counts, not independent bends. The geometric phase classifier is not
  independently labeled against video.
- P95 absolute **requested-path** bias: left 0.1658 m, right 0.1430 m and straight
  0.1636 m. This is the absolute per-frame median over supported 10/20/30 m
  sample positions, not measured vehicle-center or guardrail error.
- Initial settings snapshots in all six accepted files include raw PathOffset
  `-15` (the planner applies it as -0.15 m). Snapshots alone do not prove that
  the value stayed fixed during a drive or describe the vehicle's current settings.
- Source inspection at both logged software commits confirms the pairing of
  dPathPoints with model.position.x, the MPC position output and PathOffset units.
- Browser JavaScript/DOM interaction checks pass with the generated full report:
  six sources, filters, timeline scrubbing, empty-state handling, calibration
  labels and JSON embedding. Canvas was mocked in the local DOM check. Local
  Chromium failed to launch under the host's process/socket restrictions, so
  this is not a pixel-rendering result.
- Host-only core observer microbenchmark on 3,000 synthetic frames: median
  ~0.26 ms, P95 ~0.30 ms, excluding cereal conversion, socket subscription,
  HTTP serving and log IO. No C4/Mac live performance claim.

## Limits / next evidence

No trained driver policy, automatic tuning, steering correction, closed-loop
simulation, hardware replay, native C4 subscriber test, road validation or HUD
integration is claimed. The live HTTP and snapshot tests use synthetic input.

An external archive link referenced by an earlier lane-change report was not
retrieved: automatic approval review rejected it due to unclear authorization
for a potentially private route on an external host. Only already uploaded
Library logs were used here. The previously reported lane-change segment is not
part of this raw-log corpus; its behavior is covered only by synthetic recovery
tests, not a replay of that incident.

Detailed user logs, paths, identifiers and the generated report remain outside
the repository. The report is for the user's review. Do not treat threshold
passing or same-model lane agreement as proof of safe vehicle behavior.

## Follow-up: control source semantics

Further inspection of 55 complete local logs and the pinned controlsd source
identified a misleading UI label: dPathPoints is an MPC input, not necessarily
the selected control source. Model mode uses action.desiredCurvature directly
through smoothing and clipping. Correct the labels and expose model action,
preceding actuator command and feedback-estimated curvature separately.
27 focused tests now pass, including separation of those three signals from
MPC geometry. No controller or planner behavior is changed. Selected video
frames were paired through qRoadEncodeIdx; model geometry still is not an
independent vehicle-position measurement. User evidence remains outside Git.

## 2026-11-17: model-branch scalar baseline

Research parent: bea7574032e6f85a14cb883f417774f063fd5d64. Latest target
checked: 4a9fb70b1330e3148d6c0930827c70825e17a85e. controlsd.py and
drive_helpers.py are unchanged between the logged base and that target.

35 focused tests pass. The new scalar baseline is compared against the actual
source smoothing/clip helpers over 2,000 deterministic synthetic combinations
of speed, curvature, roll, active state and process-start state. Tests also
cover rate-only limiting (the original limited flag remains false), first
engagement versus later engagement, non-finite inputs and unsupported modes.
Ruff and whitespace checks pass. No vehicle/control code changes.

This is an initial A-baseline building block, NOT a completed A/B/C comparator.
Exact consumed-input alignment at each 100 Hz control tick, real-log command
reproduction, lane-mode baseline B and hybrid candidate C remain pending.
Do not apply this function once per 20 Hz model row and call it control replay.
No new real-log driving-performance or closed-loop result is claimed.

## Ramp control-step audit — 2026-11-17

Added local-only control_audit.py. Source remains the pinned Ioniq 5 event
commit; source/vehicle mismatch is rejected. Exact consumed model ID is taken
from controlsState.lateralPlanMonoTime (which controlsd populates from modelV2).
Other inputs remain bounded preceding samples, not proven consumed IDs.

Three contiguous user-authorized segments, including the reported ramp exit:
17,989 control steps; 17,251 computed. Median absolute curvature residual
1.5820286703924213e-11 /m; P95 3.428480156025815e-10 /m; maximum
1.6321650038453317e-09 /m. Exclusion counts (may overlap): 609 initial/gap,
127 invalid-message, 4 stale/missing liveParameters, 1 missing/stale model.
Every step is anchored to the recorded previous command: NOT closed-loop.

During the selected exit intervention, consumed model curvature rises from
about +0.0040 to +0.0061 /m and the command follows. Driver steering remains
pressed for these later samples. Navigation samples show ATC none and VTURN
selected; selected speed is above actual speed at these exit samples. This
does not establish root cause, physical applied torque, independent road
curvature, or longitudinal behavior over the entire ramp. Driver intervention
changes the pose and can affect subsequent model output.

40 focused tests pass locally, plus Ruff and whitespace checks. New tests
verify consumed-ID selection over a newer unconsumed model, missing IDs, invalid
states, lane-mode exclusion, stale state and mismatched command pairing.
Lane baseline B, hybrid candidate C and closed-loop validation remain pending.
Raw traces and source identifiers remain in the user's private report context.


## Offline C proposal — 2026-11-17

Parent: `50676db9605e628bf28aac1a48ec6abb53debae9`; target re-read:
`4a9fb70b1330e3148d6c0930827c70825e17a85e`. Event source remains
`0e462225e4184df0ee4e8cfda7b4cc7f69fbbf38`. No target/control files changed.

59 focused tests pass, with Ruff and whitespace checks. Added candidate tests
cover mirrored bends, straight geometry, bounded buildup and reversal, manual
withdrawal, inactive control, turn desire, missing geometry, tracking/saturation
and mode gates, stable recovery, invalid action/config, duplicate/reversed time
and time gaps. These synthetic cases supplement real logs; they do not provide
independent road labels. Existing baseline tests continue to pass.

Five complete retained rlogs were re-decoded with full cereal using the current
observer (5,212 planner rows). Each segment begins fresh observer/candidate
state; full segment warmup precedes the windows below. No raw data is published.

| Private corpus case | Segment window (s) | Rows | Ready candidate | Nonzero correction | Direction |
| --- | --- | ---: | ---: | ---: | --- |
| Initial left bias | 55.97–58.29 | 41 | 25 | 25 | right |
| Right bend | 25.02–44.86 | 348 | 348 | 348 | left |
| Left bend | 14.73–41.14 | 460 | 460 | 460 | right |
| Tunnel | 22.19–33.38 | 197 | 114 | 147 | right |
| Ramp exit candidate | 54.60–59.99 | 87 | 0 | 0 | none |

Initial-bias window max additional acceleration is 0.1197862654 m/s²;
right/left/tunnel maxima are 0.25 m/s². Tunnel nonzero frames exceed ready
frames because withdrawal decays instead of stepping to zero. Across its whole
segment 224 rows exceed the experimental 0.2 m/s² tracking threshold. Ramp exit
has 66 driver-pressed rows out of 87; no correction in this window. This is
correct withdrawal logic, NOT evidence the late exit is fixed. Road identity
remains a candidate label. Four previous aligned videos plus selected ramp
frames were inspected; not all videos.

All five files contain 2,091 ready and 2,186 nonzero proposal rows. These are
frame counts, not independent events or a success percentage. The small-angle
shift proxy can be as large as 0.5068 m in the low-speed initial segment; it
must not be reported as achieved centering or clearance improvement.

Remaining: verified lane-mode B, final common A/B/C 100 Hz limited comparison,
body/sensor calibration, closed-loop vehicle simulation and handover evaluation.
Closed-loop work should first reproduce the unmodified model/controller response,
then sweep speed, camera bias, delay, line loss and saturation. No calibrated
closed-loop model has been run here. No C4 or vehicle operation is authorized
by this research candidate, and no steering limits were changed.

## 2026-11-18: recoverable synthetic harness and uncertainty experiment

Research parent: `6af382f0fc615677cf8ef76b18cf4867c90392d0`.
Latest Test observed: `2b50cff45e9125501d7eb18d4d622e49c25817b7`.
The logged-source scalar baseline remains pinned to
`0e462225e4184df0ee4e8cfda7b4cc7f69fbbf38`; this is not a compatibility
certification of the current Test branch.

The prior scratch-only 128-case sweep reported 29/49/37 regressions for
0.10/0.25/0.40 m/s² correction caps, and 12/16/16 invalid comparison pairs.
The execution environment then became unavailable before source publication.
Those historical counts are not reproducible from this new v2 harness and are
not evidence that v2 passed. The original pending scratch files must be retained
and reconciled when that environment returns.

This commit reconstructs a separately labeled v2 simulator and adds an
uncertainty-interval candidate. CI is the execution source for this revision:
the local executor is unavailable. Exact test results and full synthetic
artifact are attached to the matching GitHub Actions run, not inferred here.
Tests retain the centered-model/differential-error negative case and cover
interval signs, expired/missing assumptions, reentry, input immutability,
mirroring, independently evolving feedback, faults and original rate limits.

No arbitrary common camera shift should be blamed for relative geometric error:
common translation cancels. A synthetic differential error demonstrates one
failure mode, not its presence in the vehicle. U's 0.2 m bound is an explicit
unverified assumption; +/-0.4 m cases test its violation. Neither U nor original
C is approved for deployment. Unknown bound means no initial correction.
No driver preference or PathOffset is treated as body center.

Pending: actual B planner comparison; calibrated independent road/body labels;
neural small/large model closed-loop inference; lateral/longitudinal interaction;
physical steering-response calibration; smooth actual actuator handover; and
controlled validation before any proposal is connected to vehicle outputs.

### Confirmed v2 CI and remaining failure mechanism

At faf7749c6f26cafc18d924ba56d37c0bef251816, push run
[44144928132](https://github.com/FANHAOHSIANG/openpilot-carrot/actions/runs/44144928132)
completed 104 tests, Ruff and the 320-case/three-gain sweep. Initial dcf8db4 CI
passed tests but failed two lint checks; the failure is retained in history.
For 192 bound-covered scenarios, original C had 81 regressions/28 invalid pairs;
U gain 0.25 had 12/12, gain 0.5 had 20/12, and gain 1.0 had 21/12.
For 128 bound-violating scenarios, U regressions were 20/28/60 respectively.
Gains trade improvement against degradation; none is a verified optimum.

Diagnostic commit 0eb8f7af3c3b77cf5ce1172b03e72e4df8f01100 retained all 12
covered low-gain regressions. All have nominal demand 3.24 m/s² above toy
authority 3.0 m/s². Peak displacement is already >9 m in baseline A.
The four fault variants duplicate three underlying combinations; these are
scenario counts, not twelve independent observed driving incidents.
This motivates speed feasibility analysis; it does not establish real-world
speed as the cause or show that any speed change fixes the user's ramp.

Added explicit assumed lane-boundary metrics and standalone braking-distance
feasibility tests. These new changes require their own matching-head CI.
No parameter was retuned against the failure grid, and no vehicle limit changed.

## Paired ramp acceptance corpus

Use both recorded passes in candidate reviews. The driver identified the successful pass as the onboard small model. Keep its recorded model action as the positive reference, alongside the earlier intervention. In the retained 40-second success window all 800 model rows have lateral control active and none have steeringPressed. Crossing clearance and independently measured vehicle center are unavailable. A candidate that increases exit bias, oscillation or saturation relative to this reference needs investigation before promotion. Leave unevaluated comparisons pending.

Successful recording software: 5945301512e41a791b3cd8c61d7b7b4edae3b61c. Earlier recording software: 0e462225e4184df0ee4e8cfda7b4cc7f69fbbf38. Both source trees already contain the same driving_supercombo.onnx Git blob 1aac351ca371f1f68c565470e07a530c7a65f185. Runtime model identity needs separate evidence, particularly for external inference. Treat these as two observed driving outcomes with different speeds and poses. Do not use a recorded action as a steering command or training target at a different pose. Keep full logs and location data private.

### Runtime cadence on the paired ramp recordings

Full cereal decode of the earlier ramp segment and the two newer segments spanning the successful passage. Whole-segment modelV2 metrics, not matched-frame or end-to-end latency measurements:

| Segment role | Valid publications | Median modelExecutionTime (ms) | P95 publication interval (ms) | Missing intermediate frame IDs |
| --- | ---: | ---: | ---: | ---: |
| Earlier intervention | 1030 | 47.34 | 105.73 | 170 |
| Successful approach | 1200 | 23.81 | 60.92 | 0 |
| Successful exit | 1201 | 23.82 | 63.16 | 0 |

Intervals use successive logMonoTime differences and statistics.quantiles (exclusive). Missing IDs sum positive forward gaps within each segment. All three segments have 1200 roadCameraState publications. Older logs contain explicit Jetlink timing and slow-frame messages. Model weight identity was not recovered from these measurements. Keep update cadence as a separate variable when comparing path prediction, entry speed and delayed unwind. These segment-level differences do not identify the cause of an individual intervention. The GPS pairing timestamps did not exactly match model publication times in the attempted join; no paired timing estimate is reported.
