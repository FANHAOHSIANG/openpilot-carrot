# OSM matching repair — 2026-11-12

This is an offline-tested candidate on `test/truck-clearance-204f9cca`, based on `35e0adbd`. It has not been installed or validated on the physical C4. It changes only supplementary OSM speed preview, not steering or the selected navigation owner.

## Evidence and changes

The uploaded five-segment route used phone positioning for OSM despite available device GPS. A consistent device source improved matching without the position jumps seen when switching sources only at phone timeouts. OSM now uses fresh device GPS exclusively; missing device fixes do not fall back to phone or renew timestamps. Active navigation geometry retains its existing position source.

Downloaded OSM data marks several affected roads as one-way, four-lane motorway mainlines. Device-position replay showed approximately 6–10 m centreline offsets on these sections. A valid corridor can now carry a bounded width only when every included segment has explicit one-way motorway metadata and 3–4 lanes. Links, unknown lane counts, other road classes and conflicting overlapping metadata have no allowance. The heuristic uses 1.8 m per recorded lane, capped at 7.2 m; it is not surveyed lane geometry.

Nearest-road acceptance is at most 9.2 m for these roads, with the existing heading requirement. Any additional eligible parallel corridor rejects the width-assisted match. Near-vision comparison permits only a constant offset within the corridor allowance, with a stricter remaining shape error of 1.5 m + 0.01 × forward distance. It never rotates or fits a slope to force agreement. Multi-frame confirmation and freshness checks remain. Speed uses the tighter possible lane radius, not a faster centreline cap.

`gps=device/lane=...` records the OSM source and accepted lateral offset. The offset is not a steering command. Rejected `model_mismatch` now records the measured maximum error instead of always displaying zero.

## Controlled comparison

Full route-schema decoding, segments 75–79, 5,998 eligible Carrot samples. Both variants use the same freshly downloaded tile archive; it is not verified byte-identical to the original device cache. The replay invokes production matching, GPS projection and speed calculation. It approximates receive times by publication times and worker cadence by 5 Hz, and does not simulate IPC scheduling, hardware load, actuation or exact installed parameter values.

| Status | Before | Fixed candidate |
|---|---:|---:|
| off_road | 3160 | 1161 |
| model_mismatch | 891 | 1161 |
| matched | 347 | 1033 |
| coarse_route | 171 | 1389 |

These are samples, not warning incidents or braking events. Combined off-road/model-mismatch rejection falls from 4,051 to 2,322 samples (42.7%). Raw model-mismatch count rises because substantially more samples reach visual checking; it is not eliminated. The final candidate still rejects large offsets, ambiguous roads and sparse geometry. A matched sample establishes availability of a preview, not correct physical deceleration or ground-truth road identity.

## Validation and reproduction

100 targeted tests pass (88 unit/worker tests and 12 full production-method integration tests with the route's full cereal schema). They include phone navigation remaining selected, loss of device GPS, expired/invalid width responses, wrong-fork shape, excessive offset, ambiguous parallel roads, unknown metadata and conservative curve speed. The Wiki generator/validator has 21 passing tests; both updated manual pages validate. User-documentation mapping and diff checks pass.

With full cereal schemas and `car.capnp` under `SCHEMA`, installed maps under `CACHE`, and the same ordered rlogs for each invocation:

```sh
python -m openpilot.tools.osm_preview.replay_matching --schema-root SCHEMA --cache CACHE --source phone LOGS...
python -m openpilot.tools.osm_preview.replay_matching --schema-root SCHEMA --cache CACHE --source device --lane-width LOGS...
```

Dependencies are the repository Python dependencies plus pycapnp and zstandard. No logs or precise locations are included in this commit. Disable `OsmCurveSpeedEnabled` to remove the OSM contribution; other speed sources keep their existing behavior. Physical C4 verification remains required before calling this fully resolved.
