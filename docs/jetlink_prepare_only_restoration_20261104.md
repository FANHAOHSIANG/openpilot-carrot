# Restore the Jetlink prepare-only publication contract

Status: TEST BRANCH ONLY. Unit-tested with mocked hardware, not validated for road use.

## Evidence and scope

The device logs supplied by the owner correlate dropped camera frames with invalid cameraOdometry, livePose.inputsOK=false and downstream calibration/parameter warnings. This identifies a propagation path; it does not prove the cause of every camera gap, or that Mac compute, HUD maps or Panda SPI is the sole cause.

The earlier commit `53e961cfcb78554bef5045a5c2cf8bf524a5e5f4` (2026-11-02) already implemented the Jetlink prepare-only return contract. The test branch at `103dcbbf2437e3bdf0bed2db9842f9c6bcfbc20a` does not contain that behavior: JoiningModel.run always returns parsed remote predictions, even when modeld requests prepare_only after a camera gap.

The official snapshot `14c5398fca00d298c2791ecf43f46b3e3fd6cc38` implements `ModelState.run(..., prepare_only)` by preparing camera inputs and returning None during recovery. modeld publishes modelV2, drivingModelData and cameraOdometry only when model_output is not None.

## Change

Restore the exact Jetlink model.py blob from the earlier fix, `bad7dd756aac4f5871d9df5dc68e18ca1119485f`. The remote recurrent graph and parser still consume every received camera pair. Remote hidden state and reset handling advance normally, but a prepare-only recovery result returns None instead of a publishable prediction. The next contiguous frame can resume publication with a fresh result.

This does not declare a bad pose valid, change timestamps, duplicate the last prediction, mute alerts, or relax consumer alive/valid/frequency checks. Prolonged gaps must still trigger missing-data/low-frequency protection. Fault signalling and local-model fallback on a real transport/parser error remain unchanged. N16 lossless transport, navigation metadata, HUD, vehicle control and Panda safety are not changed.

This does not reduce camera drops or make slow inference faster. Frequent gaps can reduce model publication frequency enough to trigger existing protections. It is a contract repair, not a claim that the hardware pipeline is repaired or that warnings cannot recur.

## Reproducible unit validation

Run from repository root:

```sh
python3 -m unittest discover -s openpilot/selfdrive/modeld/tests -p 'test_jetlink_prepare_only_regression.py' -v
python3 -m py_compile openpilot/selfdrive/modeld/jetlink/model.py openpilot/selfdrive/modeld/tests/test_jetlink_prepare_only_regression.py
```

The suite executes the real JoiningModel implementation with scoped mocks for GPU/transport/import dependencies. In the analysis environment the unpatched model blob `9760baf9614a582e5e51ec6bd3b3ed9804508320` failed 7 of 15 tests. The restored blob passed all 15 tests and Python syntax compilation. Cases include normal frames, isolated/consecutive recovery frames, parser/hidden-state advancement, raw-output mode, navigation metadata, unchanged local behavior, and transport/parser failure fallback.

These are not C4 camera/USB benchmarks, full rlog replay, full repository CI, or vehicle safety tests.

## Device verification gate

Keep the stable carrot-wip and official mirror unchanged. Before installing, preserve the actual device branch/SHA and local changes; never force-reset or clean build/model assets. The owner's last reported device checkout is local carrot-wip at d343fecf, not necessarily the test branch.

Any installation/restart is parked/offroad only. Verify the running manager/modeld actually loaded the new checkout. Check real cameraOdometry/modelV2 frequency and age, livePose.inputsOK/sensorsOK/posenetOK, selfdriveState and CAN/Panda health. Do not force cruise or recreate faults in road traffic. An absence of warnings while offroad is not validation. If low-frequency, stale-data, sensor, camera or SPI faults persist, retain their protections and investigate separately. Promotion to stable requires owner approval and appropriate on-device/controlled validation.
