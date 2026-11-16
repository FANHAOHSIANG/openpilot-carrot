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
