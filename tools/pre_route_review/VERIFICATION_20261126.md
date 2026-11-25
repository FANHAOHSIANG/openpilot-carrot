# 2026-11-26 verification gate — PRE / navigation lane changes / indications

## Verified
All three draft branches carried identical blobs d094186bdde75e122c29b05430b799ed6782f0f8 (shadow) and 967736619b6989c509bf2092a92b624686c281d1 (tests). Reconstructed byte-identically locally, confirmed git hash-object and ran python -m unittest -v: 7 tests passed. Synthetic diagnostics only. C4 PR workflow user docs succeeded; no control CI demonstrated. App PR had no PR-triggered workflow runs returned.

## New negative probes (observed on the exact shadow blobs)
- Route1 approach, route2 approach in same session, late route1 packet: approach accepted. Require authoritative selected route/version separate from event packet, monotonic ordering and safe reset.
- completion=true with inconsistent distance (1000 m versus expected 20 m): completed accepted. Require validated completion provenance and coherent progress.
- 99,920 m before entry: approach classification. It is a diagnostic phase, not permission for speed control; no verified approach envelope exists.

## Remaining acceptance gates
1. Capture real Amap Auto selected-route, event identity, progress, road/lane information and navigation cancellation/replan messages. Never invent mapping from a road name, timestamp or mere proximity.
2. Offline replay selected exit, unrelated exit, wrong exit, repeated old event, route replan, GPS loss, stopping navigation, successive ramps. No unbound native advice.
3. Compare raw PRE advisory, arbitration result, cruise setpoint, requested and measured acceleration and jerk. Native 10 km/h step is confirmed in validator; no actual driving acceleration trace establishes causation. Do not smooth or delay any mandatory lower camera/lead/safety constraint. No forced acceleration on release.
4. Audit existing navigation lane-change and physical indicator path; no verified proactive overtake implementation or non-PE IONIQ 5 physical signal acceptance. Verify lane-change completion, driver cancellation, blind spots, stale sensor data, signal confirmation and exit conflicts in simulation and professional controlled validation. No new steering, indicator, or overtaking commands in this review.
5. Full native control regression on both branches, signed APK build and compatibility; controlled validation before merge/release. No deployment or automatic merge.

Current draft only quarantines the unbound native PRE plus offline diagnostics. It is not the requested fully restored feature. Merge authorization is conditional on verification; gates are not met.
