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

## 2026-11-17 independent integration: guarded offline control bridge

Parent integration: `51afc23e75f14044d4ac466752b6c1fda3b32fbd` on
`test/carrot-pr52-integration-20261117`. Base remains
`b95058a5be9ffcda58f15b1dc279e4bb99083f3a`; PR #52 head is
`2be5ceb6baf80444c8ace7c976fc60dc432e5021`.

The bridge executes pinned production **pre-LaC scalar** statements extracted
from controlsd and drive_helpers after full Git blob verification. It does not
instantiate Controls or import messaging/Params. Independent A/C state persists
at 100 Hz. Actual model-mode selection is used; unsupported lane/VW paths stop
the trial without fabricating a command. Default shadow selects A; explicitly
selected isolated mode selects C in memory/local output only. No actuator sink,
startup option, vehicle deployment or production-code import was added.

Local Python 3.12 validation:

- `python -m pytest -o addopts='' --confcutdir=openpilot/tools/curve_centering openpilot/tools/curve_centering/tests -q`:
  161 passed. Four environment/config warnings (pytest plugin deprecation and
  missing asyncio/cpp plugin config support); no skipped test reported.
- `python -m ruff check openpilot/tools/curve_centering`: passed (0.17.5).
- New tests compare 2,000 combinations of the actual source statements against
  the preexisting scalar reference; source drift is rejected. Real Observer
  records reach nonzero isolated output. Driver steering/gas/brake, maneuver,
  inactive/low speed, stale/missing/future/invalid inputs, control clock failure,
  consumed-ID mismatch, same-model mutation, geometry failure, tracking failure,
  saturation/safety-limit, selected lane/VW mode and stable reentry are exercised.
- `python -m openpilot.tools.curve_centering.bridge_demo --output <new-directory>`:
  3,500 fixed-input ticks, 14 fault types. Both modes had 500 nonzero hypothetical
  injection ticks and 212 ticks with injection withdrawn but smoothing difference
  still above 1e-12 /m. Maximum A/C curvature difference 0.00173611111083532 /m.
  These are software observations, not physical handover or trajectory results.
- Both `control_bridge` CLI modes replayed the generated JSONL. All 3,500 output
  rows per mode matched the direct demo outputs exactly.
- Re-ran `python -m openpilot.tools.curve_centering.simulation --output <json>`:
  all 320 scenarios x 3 gains retained. Entire JSON is byte-identical to the
  pre-bridge run. Covered low-gain U: 12 regressions, 12 invalid pairs among
  192 cases; covered nominally feasible subset: 24 lane exceedances among 96.
- Re-ran `node openpilot/tools/curve_centering/spatial-ramp.mjs`: all eight rows
  byte-identical. The delay=0.3, bias=0.3, preview=true case still has exit error
  0.8670167948312135 m > assumed 0.85 m. Four no-preview trials do not complete.

The bridge intentionally prevents *new* injection on failed guards; it does not
silently reset production smoothing history to claim immediate physical handover.
The 212 residual ticks are an explicit remaining integration limitation. Invalid
control inputs/unsupported modes return null and stop the scalar trial; null
must never be converted to a vehicle command. Existing original-C and U negative
results are not replaced by the bridge fault-injection test counts.

The focused push workflow now includes this independent branch and retains
synthetic falsification, spatial-ramp and bridge artifacts. Local execution is
reported separately from remote CI. Full native control build, real-log bridge
replay, actuator/EPS/Panda integration, calibrated closed-loop and physical
handover tests were not performed. No C4 connection, installation, deployment,
vehicle action or raw private data publication occurred. Vehicle actuation
remains blocked by these evidence gaps and reproduced counterexamples.

## Follow-up: actual consumer shadow tap, attribution and precise blockers

Continues `fb59c77e3b670dc2332b6a5c217a6ca726302e72` on the same independent
branch. The original target branch remains untouched. No actuator assignment,
steering limit, CAN safety, controller permission or startup registration changes.
The new controlsd hook is observation-only and explicitly process-opt-in via
`CURVE_CENTERING_SHADOW=1`; default construction does not import/start it.

This supersedes the earlier description of 212 residual ticks as a generic
"handover failure". Same-state comparison proves zero new policy contribution
on every such tick. A/C have different past states; their residual decays with
the original 0.1 s filter. At the first withdrawn tick the synthetic lateral
acceleration difference is -0.226208563 m/s². Resetting the state directly to A
would require ~24.9999 m/s³ in that step against the original 5 m/s³ rate limit.
We retain the state decay, all original counts and the physical handover gap;
we do not reset state or relax a threshold to manufacture a pass.

The original 24/96 assumed-clearance failures are the same cases in A, C and
low-gain U (delay=.3, bias=.3). New candidate exceedances vs A: zero. C still has **33/96 threshold
regressions** versus A; low-gain U has 0/96 (all pairs numerically valid). These
relative results do not cancel the shared boundary failures. C's maximum extra peak in this subset is 0.0585662 m and U's is 0.0118083 m.
Representative original A/C/U peaks are 1.02051/0.987893/1.02340 m. These remain
failures. Zero-bias and zero-transport-delay ablations locate the toy-model
interaction; they are not attainable production fixes or independent events.

The separate spatial-ramp example uses no C/U at all. Its 0.867016795 m peak
occurs on exit, with 42 steps above the unmodified assumed 0.85 m clearance.
At peak, speed is 17.8465 m/s, command -0.00241478/m, actual -0.00184070/m and
road +0.000544252/m; steering authority is +/-0.00941926/m. Correction is already
inward at this late peak and not currently saturated. Removing bias, transport
delay, lag or command smoothing individually changes the counterexample. An
oracle feedforward preview using the known artificial .3+.15+.1 second lag sum
reduces peak to .426235 m. That assumes road knowledge/plant calibration absent
in real data; it is kept only as a diagnostic probe, not a vehicle implementation.
Default eight spatial-ramp rows remain byte-identical after adding trace support.

Historical evidence retrieval:

- Re-read the existing Library curve-verification report and revised paired-ramp
  report. The revised report explicitly corrects the earlier unmatched-window
  speed comparison: approximately position-matched exit speeds are similar,
  while most of the earlier exit samples already have driver intervention.
  We do not infer a solely speed-caused or solely model-caused real incident.
- The Library report is a retained analysis, not newly decoded raw evidence.
  Exact-title raw-log search did not locate the relevant later route; the current
  Library helper failed with `hosted apps tools/list request failed: network`
  both normally and with approved broader execution. No raw-log replay is claimed.
- Independently fetched successful-pass source commit
  `5945301512e41a791b3cd8c61d7b7b4edae3b61c`: controlsd and drive_helpers are
  unchanged from `0e462225e4184df0ee4e8cfda7b4cc7f69fbbf38`; both contain ONNX
  Git blob `1aac351ca371f1f68c565470e07a530c7a65f185`. This is source identity,
  not proof of which internal/external model actually executed on the vehicle.

Local checks: 174 focused tests passed (four preexisting environment/config
warnings). Tests exercise actual cereal snapshots through the consumer tap and
processor, copied data ownership, bounded queue overflow/generation reset,
exception isolation, source-mode rejection and same-state withdrawal accounting.
The entire production state_control method is compared to its pinned pre-hook
AST in off/capture/throw/real-runtime-tap configurations over 1,200 steps; every
CarControl field and selected state matches. VM, LaC, LoC, settings and hardware
are substitutes in this check; do not call it complete native torque validation.

Native `test_lateral_startup_control.py` collection remains blocked by missing
`openpilot.common.params_pyx` after installing Python dependencies. Attempted
`scons -j2 openpilot/common/params_pyx.so` stops during configuration with
`ModuleNotFoundError: No module named 'acados'`. Native and hardware tests remain
unexecuted. No vehicle was connected or operated.

Desktop capture-only performance, 3,000 calls: median 19.209 us, P95 68.372 us,
maximum 13,255.122 us (no simultaneous CPU measurement for that spike). A second
3,000-call wall/thread-CPU probe has maximum wall/CPU 339.160/339.714 us. Keep the
first negative tail; neither run includes worker contention or proves device
100 Hz deadlines. Shadow remains disabled by default. Device timing, native
controller/EPS handover, calibrated coupled dynamics and independent geometry
remain concrete blockers to actuator connection, not a generic "research" label.

## Follow-up: differential-error attribution and refinement R

- Original C remains a retained negative control. 32/33 feasible/covered
  regressions are zero-bias cases at differential error +/-0.2 m (16 each).
  Controlled zero-error interventions, preserving faults and plant parameters,
  remove all 32. This identifies false correction from uncertain model geometry,
  not measured body offset. One stale/delay/bias case remains in original C.
- New offline R combines the already-tested U gain/interval with strict quality
  withdrawal. Regression tests require immediate proposal withdrawal for missing
  or expired bounds, missing/duplicate geometry, tracking, saturation, mode and
  stale eligibility, followed by full fresh warmup. A duplicate-geometry reentry
  test initially failed and exposed premature warmup; invalid quality now also
  marks the copied row ineligible before the underlying policy update.
- R: feasible/covered 96 cases, 0 regressions, 24 exceedances. Covered/infeasible
  96 cases, 4 regressions, 12 invalid, 96 exceedances/domain failures.
  Uncovered/feasible 64 cases, 0 regressions, 16 exceedances.
  Uncovered/infeasible 64 cases, 12 regressions, 16 invalid, 64 failures.
  Invalid trajectories are not counted as valid comparisons or successes.
- No runtime/actuator wiring changed in this follow-up. R is available only to
  the offline simulator; the actual consumer tap remains C shadow, default off.
- Focused suite: 185 passed, four environment/configuration warnings. Ruff passed.
  The original sweep and spatial counterexamples are rerun, not replaced by R.
- The 0.867 m exit failure and 212 historical filter-residual ticks are not fixed.
  Independent geometry uncertainty, vehicle delay/plant calibration, native
  control-path replay and physical handover evidence remain missing.

### Native dependency recovery in the same follow-up

The earlier acados/params blocker was resolved locally. Installed the pinned
x86_64 acados/json11 wheels and the repository-declared comma dependencies
(bzip2, capnproto, eigen, ffmpeg, libjpeg, libyuv, zstd, ncurses, zeromq,
libusb, bootstrap-icons, imgui), plus pycryptodome. SCons needs the virtualenv
and capnproto `install/bin` on PATH and an absolute repository PYTHONPATH because
it evaluates subordinate scripts from other directories. The unchanged target
` scons -j2 --minimal openpilot/common/params_pyx.so ` then compiled successfully.
No native artifacts or dependency changes are committed.

The first test attempt failed all 13 cases before control execution because the
default Params directory was read-only. Setting a private scratch PARAMS_ROOT
resolved that environment failure. This exact focused test then passed 13 cases:

```sh
PARAMS_ROOT=/tmp/pr52-native-params PYTHONPATH="$PWD" python -m pytest \
  -o addopts='' --confcutdir=openpilot/selfdrive/controls/tests \
  openpilot/selfdrive/controls/tests/test_lateral_startup_control.py -q
```

These tests execute the actual torque controller and full state_control method;
IPC, settings, longitudinal control and hardware construction remain substituted.
They validate existing startup/fault behavior with shadow default off, not R
actuation, full process IPC, live CAN/EPS, or on-device timing. The earlier desktop
13.3 ms capture spike remains unresolved. Do not retain the obsolete claim that
acados or params_pyx is still the local blocker.

Two existing raw-log Library entries were located. Ordinary signed-URL downloads
failed with proxy 403; escalated download was rejected by automatic authorization
review for lacking explicit permission for those private records. No raw bytes
were obtained and no new real-log replay is claimed. Authorization is pending;
none of the logs, identifiers, signed URLs or private metadata is committed.


### Isolated observer follow-up, 2026-11-18

Actual controlsd opt-in constructor now uses ProcessShadow; the existing control
calculation and observation point are unchanged. See PROCESS_ISOLATION.md and
process-isolation-20261118.json for five 40-second comparative trials, a separate
one-second worker-stall trial and final 12-second payload confirmation.

- Focused suite: 200 passed, three configuration warnings, with
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -o addopts=''
  --confcutdir=openpilot/tools/curve_centering openpilot/tools/curve_centering/tests -q`.
  An initial invocation without isolated pytest options failed at third-party
  anyio plugin loading (pytest CallSpec2 deprecation); no product test ran then.
- Ruff: `ruff check openpilot/tools/curve_centering`, passed.
- Native startup: 13 passed, four warnings using the private Params root command
  above. These are separate from full-process synthetic timing trials.
- Original simulation regenerated and byte-compared against the retained sweep:
  identical. No failed case or threshold changed.
- Five modes of actual state_control comparisons include the new transport,
  preserving all CarControl fields and control states across 300 steps per mode.
  601-frame processor parity, exact timestamp/cache rejection, fixed packet size,
  overflow, peer death and separate actual LaC activity are covered.
- Analysis-load control publication counts improve from 130/128 to 400/400 in
  four seconds, but the one-second-stall trial retains a 33.519 ms publication
  interval. Default remains off; C4 timing and candidate actuation are unqualified.
- Private log access remained denied after the earlier explicit authorization;
  no download was retried in this follow-up and no new real-log replay is claimed.


### Owner-requested default-on shadow follow-up

Only the independent integration branch changes its constructor environment
default to 1. Explicit 0 remains disabled; unset/1/0/empty/invalid values are
covered. No actuator expression, state_control logic, CAN protection or limit
changes. English/Korean settings and log-retrieval guides updated. No Params or
settings-catalog entry exists for this process environment option, so generated
per-setting Wiki pages are not applicable.

- Focused suite: 206 passed, three configuration warnings. Ruff passed.
- Native lateral startup: 13 passed, three configuration warnings.
- Full desktop controlsd, default environment absent: 40 seconds, actual
  logmessaged with only its file destination redirected to private scratch.
  Saved 24 observation events (11 nonzero comparisons) and two stop events.
  One-second stall and worker exception yielded transport_TimeoutError and
  transport_ConnectionRefusedError; both workers stopped.
- Explicit environment 0: 12 seconds, no worker, no capture and no shadow records.
- Swaglog export and synthetic zstd rlog export matched all 26 records. The first
  fixture used an unsupported .rlog suffix and failed before export; compressed
  .rlog.zst passed. No private log was downloaded or replayed.
- New run max publication interval 29.439 ms; older 33.519 ms failure and all
  policy/geometric negatives remain. Default-on is the owner's requested test
  branch behavior, not evidence of C4 timing qualification. Full aggregate in
  DEFAULT_SHADOW_VALIDATION.json; usage and disable semantics in DEFAULT_SHADOW.md.


### Camera alert follow-up: scheduler inheritance

Concrete defect found: multiprocessing observer inherited controlsd FIFO53/core6
on device, while prior PC timing tests skip those settings. Replace observer
launch with explicit pre-exec SCHED_OTHER, nice19/background device affinity before
analysis import, no controlsd re-import/helper process and no realtime fallback.
See SCHEDULER_FIX.md / SCHEDULER_FIX_VALIDATION.json. 208 focused tests and Ruff
passed. New native-IPC 40-second trial recorded24 observations and2 stops, all
reported worker policy0/nice19; publication peak26.664ms remains negative.
SCHED_BATCH inheritance probe and spawn contract checks are desktop evidence;
C4 FIFO/affinity execution and photo causality remain unverified. No device access,
private-log download, camera alert threshold or actuator change.
