# Ioniq 5 non-PE SPAS offline research

Scope: `HYUNDAI_IONIQ_5` (2023), logical ECAN 0. Reviewed test base `1fef6217` and upstream `ajouatom/openpilot` `carrot-wip` at `162da468`. This change adds a desktop evidence reader and regressions around the existing session. It does not change the vehicle runtime or any settings.

## What was observed

- The READY/P commissioning screenshot shows 177 valid samples each at 0x165 and 0x16A, extended-session confirmation, two `7F 28 22` replies, default-session confirmation and confirmed fresh neutral stock reception. Handoff and lamp feedback were false. The second refusal cannot be assigned to a specific outgoing request without the original timed TX/RX capture.
- ISO 14229 UDS service `0x28` is CommunicationControl and NRC `0x22` is ConditionsNotCorrect. This identifies the rejected service and general reason, but does not expose the ECU's internal gate. The accepted extended session, stock traffic and healthy parked preflight do not attest readiness for communication handoff. A hypothesis about trim, firmware, interlocks or gateway policy requires independent evidence.
- A separate full-schema rlog replay reproduced 5,951 valid CAN events, 5,933 stock-ready samples, 5,911 neutral samples and 3,001 valid frames per SPAS address on bus 0. It contains no live response frames from the parking diagnostic endpoint. Its `carParams.carFw` and a separate startup segment identify `parkingAdas` with bus 0 and a response at 0x7B9. None of the 61 readable unique archived segments showed `7F 28 22` on that endpoint and bus. One additional candidate failed decoding. The four screenshot replies are therefore a real outcome modeled with simulated timestamps, not a raw replay of the rejected transaction.

## Which path the evidence supports

| Mode | What it checks | Observed limits |
| --- | --- | --- |
| Normal acknowledged path / parked 1–2 | Extended session, communication acknowledgement, OEM traffic quiet, then bounded indication and restoration | This vehicle accepted the session and refused communication control. Recovery and neutral stock reception were reported. |
| PE 15–16 | Reproduces the original experimental SPAS sequence without the normal acknowledgement and stock-silence gates | Historical left test hit CAN errors while stock traffic continued and stopped with no lamp feedback. The right case was not run in that record. |
| PE 17–18 | Separate counter-aware stalk replay without an APRK handoff | Historical left trial ended without confirmed lamp feedback. The right case was not run in that record. |

The direct modes are gated on `HYUNDAI_IONIQ_5_PE` in `openpilot/selfdrive/car/hyundai_spas.py`. Upstream `12ae3051` introduced the acknowledged path, `5a3889e6` and `e4e93acc` describe the original-sequence comparison and its outcome, and `892fae1a` adds the stalk comparison. See `docs/canfd_spas_blinkers_20261026.md`. There is insufficient evidence to introduce a new active parked trial for non-PE.

## Read local evidence

```sh
python -m tools.jetlink.spas_replay --rlog /path/to/local/rlog.zst --bus 0
python -m tools.jetlink.spas_replay --reply '7f2822'
python -m pytest tools/jetlink/test_spas_replay.py
```

The rlog path uses the full cereal schema and reads recorded `can`, `carState` and `carParams` only. Parking ECU firmware records include the original read request and captured data when present. The repository identifies `0x7B1` / `0x7B9` for this endpoint. Stored UDS data identifies DIDs `F110` (description) and `F18B` (manufacturing date) for this capture. The reply decoder accepts complete UDS data-by-identifier and DTC-by-status replies. A DTC status of “unknown” should be retained unless a complete read exists. Multi-frame fragments in an rlog are counted separately and are not interpreted as complete replies. Capture files, route identifiers and vehicle-specific metadata are kept outside this PR.

## Evidence still needed

Obtain the Hyundai service report for the matching parking ECU/part number, including hardware and software identification, active and historic DTCs, and any documented firmware applicability for this trim. If the original commissioning capture is available, correlate TX/RX on the same monotonic clock with ECU identity and stock continuity. Any future active validation would require a separate review based on that evidence. Physical direction-lamp operation and road use remain unverified.
