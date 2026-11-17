# HOLD — 2026-11-18

Target re-read: e63ca079953b58bed02117914d060ac36e9a0f01. Official: 446fa79624644c79db81b788d665abb6830ddff7. Tony: a2fbae27fd289a25cbf3212fb7714875e8543d8a.

Original workspace was absent; unpushed classic repair and its tests were not recoverable. Re-cloned target and merged held d55ff146 candidate without conflicts, preserving three-map pre-adjust. This branch checkpoints that combination only, not the new upstream tips.

Local official merge dd559483 resolves interface/values conflicts by keeping independent angle 512 and Kick 32768 while adopting observed protocol admission; needs regressions. Attached official-review.patch is the review delta. Tony's subsequent merge has seven unresolved files: navigation feature, Python navigation tests, navigation_map.js, navigation.html, JS navigation tests, generated cockpit.js and asset-manifest. New text-query favorites and temporary geocoding must be reconciled with disabled search/manual coordinates without deleting tests. Attached combined conflict diff is diagnostic, not an apply-ready patch.

CPU native libraries and C safety library compiled successfully. Fresh focused C flags tests: 16 passed, 2 failed (classic ALT_LIMITS_2 boundary cases), exit 1. Previous unpushed 20-case stream pass is historical and cannot qualify this reconstructed tree. Full integration, final safety baseline comparison, assets and CI are incomplete. No target ref updated. Do not deploy.
