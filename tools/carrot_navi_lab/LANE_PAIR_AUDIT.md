# Offline lane pairing audit
This tool consumes existing C4 Web lane-observe schema 3 JSONL. It does not read rlog directly, transmit messages, alter HUD or control code, or assume that a recommendation icon index is a physical lane index.
Run from this directory:
```sh
node lane_pair_audit_cli.mjs --self-test
node lane_pair_audit_cli.mjs carrot-lane-observe.jsonl
```
The audit distinguishes missing streams, time mismatch, missing/withdrawn candidates, positive advice, insufficient local geometry and co-observation. It counts distinct navigation envelope timestamps separately from paired model observations. Clock reversals split epochs; separate trips should be processed separately. Schema 3 has no route identity or explicit original candidate deadline, so the tool trusts the observer's at-capture candidate validity and cannot certify route transitions, physical lane association or native geometry. Count equality is diagnostic only. Absolute mapping and control usability are always false.
15 synthetic regression cases are provided; real driving files were not available to this implementation session. No accuracy, road validation or native geometry claim.
