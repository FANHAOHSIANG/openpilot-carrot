# openpilot 0.11.3 development merge trial

Date: 2026-11-02

## Pinned inputs

- Base: FANHAOHSIANG/openpilot-carrot carrot-wip, 8c4a5b89f8ab3238acd1e6aa60474e643765b83a.
- Candidate upstream: commaai/openpilot master, 54ce79f01efd78e4327eb2ce6b4e107db7de359f. This is a pinned development snapshot, not a verified v0.11.3 release tag.
- Experiment: experiment/carrot-wip-op0113-20261102.

## Actual results

A filtered, non-shallow clone was fetched locally. `git merge-tree --write-tree --name-only origin/carrot-wip FETCH_HEAD` refused with `fatal: refusing to merge unrelated histories`. Carrot has a c4-v1 root at ecf4d58ce; no common merge base was found against this upstream history.

A second dry run permitting unrelated histories was attempted. It did not complete: lazy object retrieval failed with `upload-pack: not our ref` / `could not fetch ... from promisor remote`. No merged tree or buildable result was established.

A complete tree-metadata comparison succeeded: Carrot 6321 paths, upstream 1224 paths; 735 shared paths have different Git object IDs, 5300 paths occur only in Carrot and 203 only in upstream. These are divergence counts, NOT 735 verified textual merge conflicts. Upstream submodule/vendor representation also differs; path counts do not quantify implementation size.

Critical differing paths include cereal/log.capnp, longitudinal_planner.py, longitudinal_mpc_lib/long_mpc.py, plannerd.py, modeld.py, selfdrived.py, launch_env.sh and common/version.h.

## Source review

Official longitudinal planning always considers MPC, cruise and model acceleration candidates, includes AccelBoost, and no longer uses selfdriveState.experimentalMode. Carrot still selects acc/blended through experimentalMode and carrot.update/carrot.mode, and integrates Carrot-specific stopping, preview and coasting behavior. Official lead.present versus Carrot lead.status is another schema/interface difference. Replacing only the official planner would not preserve these interfaces.

## Status and next implementation boundary

This branch contains unchanged carrot-wip runtime plus this report. It is NOT a merged 0.11.3 build. No version bump, model switch, safety change, vehicle installation or hardware validation was performed. No build/replay tests were run because no candidate implementation was produced.

Recommended continuation: port a bounded Autospeed planner path into this experiment while retaining Carrot mode/stop/navigation ownership and Jetlink/HUD interfaces, then validate schema compatibility, longitudinal simulation/replay and model fallback before any vehicle evaluation. Full-master merging requires a deliberate vendor/submodule and history integration strategy first. Do not force-select upstream files or weaken model/pose/safety validation to make the merge pass.
