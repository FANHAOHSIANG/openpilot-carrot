# C4 auxiliary lane inference cooldown candidate

Status: offline scheduling regression passed; NOT validated on the vehicle.
Base: a0b1747eb1fbc487d4f2a54bf584eae19f93bf6b (the failing trip's C4 commit).
Test branch: fix/xiaoge-lane-cooldown-20261109.

## Evidence and scope

The Mac runtime candidate from carrotMAC-HUD PR #6 did not eliminate the reported
alerts in trip 000003b0--fcb09c99aa. Segment 6 had no observed xiaoge_data process;
segments 7 onward did, with roughly 108–114% of one CPU core in later segments.
Between segment 6 and segments 9/11, Jetlink USB send time increased from about
3.7 ms to 6 ms while Mac compute stayed near 35 ms. Road camera remained 20 Hz;
model output fell to about 15.8–16 Hz. This is correlation, not proof that this
process is the sole cause of communication and localization alerts.

The lane loop has a demonstrable scheduling defect under overload: it schedules
from the previous start, but lane inference takes approximately 1.2–1.3 seconds
against a 0.4-second configured period. It therefore starts again immediately.

The patch uses max(configured period, twice previous inference duration) as the
start-to-start period. For steady 1.3-second jobs it leaves about 1.3 seconds
between jobs. This bounds steady inference wall-time duty to approximately 50%;
it is not an OS CPU quota and does not promise a specific CPU percentage or
primary-model rate. No inference jobs are queued. The loop continues receiving
frames, refreshing settings, and servicing requested snapshots during cooldown.

Tradeoff: auxiliary lane recognition updates less frequently under load.
Existing lane freshness checks can therefore expire and use their existing
fallback. No freshness, calibration, location, communication, or engagement
checks are relaxed. BSD scheduling, model calculations and primary model timing
are unchanged. This patch does not establish safe on-road operation.

## Validation

`python openpilot/selfdrive/carrot/tests/test_xiaoge_lane_pacing.py`

Five deterministic tests execute the actual production road-camera method with
fake camera/time/inference dependencies: slow inference cooldown and snapshot
progress, normal cadence, longer configured interval, live interval changes,
and recovery from an inference error. Original source fails the overrun test
and passes the other four. Patched source passes all five. Python compilation
passes. Full native cereal/vision and hardware integration were not run here.

## Install on a parked C4

Keep the Mac version and model unchanged for this comparison. Run in the C4
terminal, not the Mac terminal. These commands require the exact observed base
and a clean tracked working tree; they stop instead of overwriting local edits.

```sh
(
  set -eu
  cd /data/openpilot
  test "$(git rev-parse HEAD)" = a0b1747eb1fbc487d4f2a54bf584eae19f93bf6b
  git diff --quiet
  git diff --cached --quiet
  git fetch https://github.com/FANHAOHSIANG/openpilot-carrot.git fix/xiaoge-lane-cooldown-20261109
  git branch backup/before-xiaoge-cooldown-20261109 HEAD
  git switch -c fix/xiaoge-lane-cooldown-20261109 FETCH_HEAD
  git log -1 --format='%h %s'
)
```

Only after successful checkout, reboot normally. Do not use the Mac
03-Update.command to install this C4 patch. If the exact-base check fails,
inspect `git status --short` and `git log -1 --oneline`; do not force/reset.
Rollback while parked: `git switch backup/before-xiaoge-cooldown-20261109`, then
reboot. Dirty-tree conflicts must be resolved without discarding local work.

## Required device verification

Confirm branch/commit; record inference latency and rate, xiaoge_data CPU,
Jetlink USB send/exchange/Mac compute, modelV2 rate, calibration/pose validity,
and alerts. Compare the same model and Mac version. If CPU pressure drops but
model rate remains low, investigate USB/other consumers rather than weakening
communication or localization checks. Do not engage assistance while alerts
remain. No claim of a completed vehicle fix until new logs confirm recovery.
