# OSM preview refinement validation

Target: `test/truck-clearance-204f9cca`. Comparison parent: `fa8bf839d06d1d1549c2ff737a514e6f3ef46e4c`.

## Changes

- Remove width-tag-only ambiguity rejection; nearby competing corridors still reject.
- Preserve confirmation only across exact ordered forward OSM edges with at least 60 m remaining, not changed forks or navigation owners. Time gaps and stale inputs still invalidate confirmation.
- Preserve independently valid near-model confirmation through sparse geometry; report `coarse_straight` separately. No invented curvature or new speed ceiling from sparse geometry.
- Bounded recent unique positions can exclude disconnected alternative roads. Connected forks/merges, impossible jumps, expired anchors and unexplained parallel roads remain rejected. Ambiguous samples cannot renew history.
- Offline replay now reports simulated ceiling event onset, minimum ceiling and recorded speed, including held ceilings, rather than only accepted counts.

## Verification

94 focused unit cases and 12 full-method integration cases passed; 21 Wiki generator/validator tests passed. Generated EN/KO OSM pages accept the staged Wiki patch and validate. No new settings, defaults or driver control permissions were added.

78 unique segments, 89,809 model-time samples, approximately 76.8 minutes; 77 complete and one truncated tail. Segment state reset independently. Same device GPS projection and installed map cache in both variants, matching at 5 Hz, preview updates at recorded model publication times. This comparison isolates this patch from fa8, not phone-versus-device sourcing. Previous baseline counts reproduced exactly.

Matched samples: **13,486 → 13,773**. All 13,486 previous matches retained; **287 additional matches, zero match regressions**. No `road_tracked` events occurred in these recordings: trajectory disambiguation has synthetic coverage only, with no demonstrated field gain here.

`000003ae--6673ff9856--29`: first simulated ceiling below recorded speed moves from 1800.215 to 1799.937 (0.278 s earlier), restoring the formerly delayed interval. At 1799.937 the new ceiling is 56.3 km/h versus recorded 71.1 km/h; fa8 supplied no constraint (250 sentinel). This is not measured brake actuation.

Three segments gain newly matched samples with ceilings below recorded speed: c1/9 (7), ae/29 (4), aa/5 (7). These are candidates for video/vehicle review, not proven correct braking or false-brake labels. Earlier valid constraints also change gradual-release state, so later ceilings can differ.

## Limits

This is a deterministic matcher/preview replay, not complete process/IPC replay or physical steering/braking validation. It does not reproduce Jetlink/GPU contention, lagging warnings, actual actuator response, or all other speed-limit owners. Maps are the current downloaded cache, not proven identical to historical device maps. No claim that all requested custom vehicle functions are fault-free. Sparse missing geometry remains unavailable; no GPS remains unavailable.

## Event onset comparison

Times are monotonic seconds from the original logs. Each onset is a crossing below recorded vehicle speed, not a distinct mapped curve or a driver-visible warning. Unchanged segments omitted.

| Segment | fa8 onsets | candidate onsets |
|---|---|---|
| 000003ae--6673ff9856--29--rlog(1).zst | [1800.215] | [1799.937] |

All simulated below-speed samples, including held constraints: 2435 → 2439.

## Per-segment acceptance

| Segment | samples | retained | added | lost |
|---|---:|---:|---:|---:|
| 00000359--7eecdbe596--0--rlog.zst | 1109 | 0 | 0 | 0 |
| 0000035a--33998eb6c3--0--rlog.zst | 1115 | 0 | 0 | 0 |
| 0000035a--33998eb6c3--12--rlog.zst | 1048 | 641 | 6 | 0 |
| 0000035a--33998eb6c3--9--rlog.zst | 1047 | 531 | 5 | 0 |
| 00000369--9d22b530fe--0--rlog.zst | 1126 | 622 | 0 | 0 |
| 00000369--9d22b530fe--6--rlog.zst | 1182 | 292 | 0 | 0 |
| 00000369--9d22b530fe--7--rlog.zst | 1184 | 97 | 0 | 0 |
| 00000369--9d22b530fe--8--rlog.zst | 1192 | 56 | 0 | 0 |
| 00000369--9d22b530fe--9--rlog.zst | 1189 | 40 | 0 | 0 |
| 00000384--8d2511ca94--1--rlog(1).zst | 1201 | 0 | 0 | 0 |
| 000003aa--349a7da68e--3--rlog(2).zst | 1187 | 376 | 13 | 0 |
| 000003aa--349a7da68e--4--rlog(1).zst | 1181 | 0 | 2 | 0 |
| 000003aa--349a7da68e--5--rlog(2).zst | 1169 | 755 | 23 | 0 |
| 000003ae--6673ff9856--1--rlog(1).zst | 1198 | 0 | 0 | 0 |
| 000003ae--6673ff9856--2--rlog(1).zst | 1197 | 0 | 0 | 0 |
| 000003ae--6673ff9856--29--rlog(1).zst | 934 | 59 | 16 | 0 |
| 000003ae--6673ff9856--3--rlog(1).zst | 1200 | 0 | 0 | 0 |
| 000003b0--fcb09c99aa--10--rlog.zst | 964 | 201 | 5 | 0 |
| 000003b0--fcb09c99aa--11--rlog.zst | 956 | 137 | 0 | 0 |
| 000003b0--fcb09c99aa--13--rlog(1).zst | 974 | 231 | 0 | 0 |
| 000003b0--fcb09c99aa--6--rlog (1).zst | 1095 | 0 | 0 | 0 |
| 000003b0--fcb09c99aa--7--rlog.zst | 1030 | 0 | 0 | 0 |
| 000003b0--fcb09c99aa--8--rlog.zst | 1036 | 0 | 0 | 0 |
| 000003b0--fcb09c99aa--9--rlog.zst | 944 | 56 | 0 | 0 |
| 000003b3--7a06e99d02--1--rlog.zst | 1198 | 0 | 0 | 0 |
| 000003b3--7a06e99d02--2--rlog (1).zst | 1196 | 91 | 19 | 0 |
| 000003b3--7a06e99d02--3--rlog.zst | 1199 | 28 | 0 | 0 |
| 000003b3--7a06e99d02--5--rlog.zst | 1200 | 0 | 0 | 0 |
| 000003b3--7a06e99d02--6--rlog.zst | 1199 | 458 | 19 | 0 |
| 000003b4--7a97814cf0--0--rlog.zst | 1118 | 0 | 0 | 0 |
| 000003b4--7a97814cf0--1--rlog.zst | 1199 | 141 | 0 | 0 |
| 000003b4--7a97814cf0--4--rlog.zst | 1198 | 332 | 0 | 0 |
| 000003b4--7a97814cf0--5--rlog.zst | 1199 | 34 | 0 | 0 |
| 000003b4--7a97814cf0--8--rlog.zst | 1200 | 579 | 0 | 0 |
| 000003c1--f9661eb0cb--10--rlog.zst | 1193 | 0 | 0 | 0 |
| 000003c1--f9661eb0cb--11--rlog.zst | 1199 | 141 | 6 | 0 |
| 000003c1--f9661eb0cb--12--rlog.zst | 1195 | 301 | 7 | 0 |
| 000003c1--f9661eb0cb--13--rlog.zst | 1192 | 0 | 0 | 0 |
| 000003c1--f9661eb0cb--14--rlog.zst | 1186 | 478 | 0 | 0 |
| 000003c1--f9661eb0cb--15--rlog.zst | 1175 | 656 | 0 | 0 |
| 000003c1--f9661eb0cb--16--rlog.zst | 1175 | 406 | 0 | 0 |
| 000003c1--f9661eb0cb--17--rlog.zst | 1197 | 0 | 0 | 0 |
| 000003c1--f9661eb0cb--2--rlog.zst | 1192 | 337 | 13 | 0 |
| 000003c1--f9661eb0cb--3--rlog.zst | 1188 | 301 | 19 | 0 |
| 000003c1--f9661eb0cb--4--rlog.zst | 1179 | 893 | 66 | 0 |
| 000003c1--f9661eb0cb--5--rlog.zst | 1193 | 0 | 0 | 0 |
| 000003c1--f9661eb0cb--6--rlog.zst | 1200 | 139 | 0 | 0 |
| 000003c1--f9661eb0cb--7--rlog.zst | 1192 | 0 | 0 | 0 |
| 000003c1--f9661eb0cb--8--rlog.zst | 1187 | 40 | 0 | 0 |
| 000003c1--f9661eb0cb--9--rlog.zst | 1186 | 383 | 10 | 0 |
| 000003cc--8d19bf55d5--75--rlog.zst | 1198 | 596 | 25 | 0 |
| 000003cc--8d19bf55d5--76--rlog.zst | 1200 | 334 | 13 | 0 |
| 000003cc--8d19bf55d5--77--rlog.zst | 1199 | 0 | 0 | 0 |
| 000003cc--8d19bf55d5--78--rlog.zst | 1199 | 390 | 0 | 0 |
| 000003cc--8d19bf55d5--79--rlog.zst | 1195 | 0 | 0 | 0 |
| 99411088c9cfd064_00000032--8f912403f1--0--rlog.zst | 694 | 0 | 0 | 0 |
| 99411088c9cfd064_00000032--8f912403f1--6--rlog.zst | 1200 | 0 | 0 | 0 |
| 99411088c9cfd064_0000003c--01991de3d6--4--rlog.zst | 1198 | 226 | 0 | 0 |
| 99411088c9cfd064_0000004f--858ff9d82b--0--rlog(2).zst | 827 | 0 | 0 | 0 |
| 99411088c9cfd064_0000004f--858ff9d82b--15--rlog.zst | 1200 | 0 | 0 | 0 |
| 99411088c9cfd064_0000004f--858ff9d82b--20--rlog.zst | 1199 | 0 | 0 | 0 |
| 99411088c9cfd064_0000004f--858ff9d82b--22--rlog.zst | 1198 | 0 | 0 | 0 |
| 99411088c9cfd064_0000004f--858ff9d82b--23--rlog.zst | 1200 | 0 | 0 | 0 |
| 99411088c9cfd064_0000004f--858ff9d82b--24--rlog.zst | 1200 | 41 | 0 | 0 |
| 99411088c9cfd064_0000004f--858ff9d82b--25--rlog.zst | 1199 | 200 | 0 | 0 |
| 99411088c9cfd064_0000004f--858ff9d82b--26--rlog.zst | 1200 | 91 | 0 | 0 |
| 99411088c9cfd064_0000004f--858ff9d82b--27--rlog.zst | 1199 | 635 | 14 | 0 |
| 99411088c9cfd064_0000004f--858ff9d82b--28--rlog.zst | 1197 | 0 | 0 | 0 |
| 99411088c9cfd064_0000004f--858ff9d82b--31--rlog.zst | 1199 | 50 | 6 | 0 |
| 99411088c9cfd064_0000004f--858ff9d82b--32--rlog.zst | 1199 | 194 | 0 | 0 |
| 99411088c9cfd064_0000004f--858ff9d82b--34--rlog.zst | 1200 | 897 | 0 | 0 |
| 99411088c9cfd064_0000004f--858ff9d82b--35--rlog.zst | 1200 | 0 | 0 | 0 |
| rlog.zst 12 | 1116 | 0 | 0 | 0 |
| rlog.zst 2 | 1179 | 0 | 0 | 0 |
| rlog.zst 3 | 1153 | 0 | 0 | 0 |
| rlog.zst 4 | 1163 | 0 | 0 | 0 |
| rlog.zst 6 | 1162 | 0 | 0 | 0 |
| rlog.zst 9 | 1143 | 0 | 0 | 0 |
