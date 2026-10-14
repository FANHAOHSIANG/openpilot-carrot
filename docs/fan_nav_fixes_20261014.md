# Mac RL Nav: instruction serialization and auxiliary CPU work

This patch is based on carrot-nav `3cacda59de759b933a6038397564b05a5e8a0459`.
Publication is in the user's fork, on `carrot-nav-fixed`; it is not a change to
ajouatom's official branches or an installation on the vehicle.

## Observed failure and changes

- Route instruction generation fails when NumPy cumulative distances are assigned
  to Cap'n Proto `allManeuvers.distance`. Convert that boundary value to Python
  `float`. This preserves distances and route ownership, and allows instructions
  to publish. Map availability still requires current GPS, guidance and tiles.
- Xiaoge auxiliary vision accounted for approximately 147% of one CPU core in
  process samples. Its server now keeps OpenCV on one worker and inherits nice
  15 (or an already lower priority) on the existing little-core mask. Driving,
  camera, DM, control, planner and locationd placement are unchanged. Inference
  intervals, confidence thresholds, timestamps and expiry policies are unchanged.
- Avoid the unused road-plane view when lane inference is not due. Reject mask
  crops that cannot reach the existing lower-half boundary before matrix work;
  they already produced no candidate. Do not change masks or thresholds.
- The data broadcaster still updates subscriptions and sequence every tick, but
  skips collecting/serializing full snapshots when no TCP recipients exist. A new
  client receives current data on the next tick, at the existing cadence.
- The already throttled locationd invalid-input reason goes to cloudlog so future
  route logs retain the failing service and timing/sanity reason. Validity gates,
  drop policy, calibration and filter limits are unchanged.

## Validation and limits

40 focused tests pass on Linux with full cereal/pycapnp serialization, real ONNX
auxiliary inference, padded NV12 checks, idle/reconnected broadcaster behavior,
low-priority worker setup, and throttled diagnostic logging. The small boundary
harness executes the production methods using AST loading solely to avoid
unavailable native imports; it does not replace their bodies. Native IPC/service
scheduling and physical GPU/USB operation remain target checks.

Four private route-preview images gave identical lane results across 12 runs
and identical blindspot results for eight side/image samples with one versus two
OpenCV threads. On this desktop, lane mean wall time increased from about 53.6ms
to 77.7ms; blindspot mean process CPU work decreased from about 88.2ms to 19.8ms,
while wall time was about 18.6ms versus 19.8ms. Small, sequential desktop samples
are not C4 timing, recognition accuracy, an isolated total-service speedup or
proof that inference remains within its expiry budget under target load.

The baseline drive's steady model publication was around 19.1Hz with roughly
47.5ms mean model execution, and intermittent invalid camera odometry/calibration
inputs. This patch does not claim to resolve every drop, localization alert or
USB interruption. Fixing navigation also activates previously idle map-render
work, which may add CPU demand. Compare per-core load, DM/model cadence, data
freshness, USB timings and pose input validity with actual navigation and HUD.
Do not hide warnings, relax timing checks, truncate model outputs, or disable DM.

## Install and verify

While parked/offroad, use the fork's `carrot-nav-fixed` branch. Back up local
vehicle edits and settings before switching; do not force-reset a dirty checkout.
These are Python changes and do not change model weights or require a Mac App
update. Restart through the usual offroad startup path after applying them.

Confirm `navd.failed_to_compute` with unsupported NumPy distance no longer
appears, `navInstructionCarrot` becomes valid, and the map reports ready only
with real data. Keep the existing RL Nav pin and USB mode. Compare CPU by core,
model/DM cadence, auxiliary inference result ages and localization diagnostics.
Desktop/CI validation does not establish physical display or driving behavior.
