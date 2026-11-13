# Ioniq 5 CAN-FD: comma-only indicator commissioning

The existing `carrot-wip` implementation already supports the acknowledged SPAS
transport independently of a Mac/Jetson inference host. The older
`carrot-wip-map-hud` branch does not include that transport. This change adds a
commissioning CLI, not a new CAN controller, a Mac USB-CAN driver or an automatic
enablement. No model, steering, longitudinal, Panda or indicator policy is changed.

The available 2023 Ioniq 5 recording has both required bus-0 messages: 3,001
SPAS1/24 and 3,001 SPAS2/32 with valid CRC and advancing counters. Full-schema
replay through the new monitor sees 5,951 CAN events, 5,933 stock-ready samples
and 5,911 neutral/driver-ready samples. There are no captured diagnostic replies.
This establishes recorded preconditions, not live readiness, APRK handoff,
physical illumination, restoration or road validation. Other vehicles' prior
SPAS failures in `canfd_spas_blinkers_20261026.md` must not be attributed to this
2023 vehicle, and matching frames do not resolve those failure modes.

## Normal delivery

Pull/restart using the normal update flow on `FANHAOHSIANG/openpilot-carrot`,
branch `carrot-wip`. Do not overwrite a dirty vehicle checkout or transplant this
one script into the older map-HUD branch: it lacks the underlying transport.
Preserve local changes and confirm the installed branch before updating.
The SPAS implementation requires the matching normal Panda build. The CLI checks
live Panda's SPAS selection, but does not attest firmware signatures or replace
the normal boot/build checks. Mac Jetlink is not modified by this change.

## First step: read-only

With the vehicle stationary in Park and normal services running:

```sh
cd /data/openpilot
python -m tools.jetlink.spas_check
```

This command does not write Params or publish CAN. It observes exact ECAN frames,
CRC/counter continuity, neutral driver input, fresh Park/standstill/inactive
control state and at least three seconds of stable Panda health. Missing/stale,
future, unsupported or conflicting observations fail the preflight. Existing
SPAS selection is printed separately; a preflight pass does not enable it.

## Explicit stationary test

Only after reviewing a live preflight, select the existing
`CanfdBlinkerControl` / `CAN-FD SPAS indicators (trial)` setting in Carrot Web
and reboot normally. Keep `AutoBlinkerControl=0` and `CanfdBlinkerTest=0` for this
isolated commissioning test. Do not select direct/coexistence modes 3–18.
With ignition on, actual Park, zero speed, no active controls and pedals/stalk
released, run one direction:

```sh
python -m tools.jetlink.spas_check --test left
```

The CLI repeats preflight, verifies selected CarParams and live Panda SPAS flags,
then selects only the existing three-second acknowledged test 1 (left) or 2
(right). It does not publish raw CAN. It cancels on stale state, motion/control,
driver input, changed settings or CAN-health/rejection-count changes. A `finally`
block resets the test to zero after normal completion or exceptions. The existing
controller separately bounds the trial duration; process termination is not proof
of completed ECU restoration. No automatic retry or fallback is added.

The result separates ECU handoff ACKs, CAN-derived lamp feedback, and subsequent
restore ACK plus fresh neutral stock reception with stable health. Requested
commands and received feedback are not independent wire delivery or visual
confirmation. Observe the actual vehicle lamps. A failure or unconfirmed restore
must end this commissioning attempt; do not enable automation or repeat on the
other side to bypass it. Restore the trial option to OFF via normal settings and
reboot if the transport cannot be commissioned; confirm OEM stalk/parking
functions normally. Do not use direct modes to force a positive result.

A successful stationary left test does not certify right-side behavior, holding,
driver override, Mac inference co-load or any driving scenario. A right test is
separate, explicit and only appropriate after successful restoration/inspection.
Automatic operation remains unvalidated and is not enabled by this deliverable.

## Validation

The new monitor/CLI tests cover bad CRC, counter gaps, duplicate/future/stale
samples, bus selection, driver input, fresh parked control/health gates,
read-only default behavior, explicit left/right mode selection, automatic-mode
rejection and exception cleanup. Actual Params/native messaging in CLI lifecycle
tests are replaced with deterministic desktop adapters, not vehicle services.
Existing SPAS state-machine tests and recorded full-schema CAN replay supplement
these tests. Native device build, actual ECU handoff and physical lamp testing
remain pending on the user's C4.

## Long-term upstream test branch diagnostics (2026-11-13)

For FANHAOHSIANG's long-term test installation, the target is
`test/carrot-wip-upstream-20261104`. The switches, read-only preflight and
acknowledged tests described above are already integrated. Keep
`CanfdBlinkerControl=0` by default; do not enable automatic operation merely
because offline messages match. No additional physical wiring is established
as necessary by the available RX evidence.

The `hyundai_spas_diagnostic` structured log event is emitted every second when
selected and every ten seconds when disabled. The original `hyundai_spas`
transition event is preserved. Inspect the recorded rlog logMessage stream or
card process logs. Fields distinguish:

- `enabled`, `ecan`: effective startup selection, not the requested toggle.
  Disabled means the startup flag is absent or the vehicle is passive; it does
  not prove missing vehicle hardware. Reboot is required after toggle changes.
- `stock_ready`, `stock`: per-ID accepted CRC/counter sequence, counter and age.
  Missing ages are JSON null. RX readiness is not ECU handoff approval.
- `driver_age_s`, `driver_valid_count`, `driver_override`: validated driver-input
  freshness and override latch.
- `trial_rejection`: parked guard, unsupported model-specific trial, busy
  session or stock/CAN readiness rejection. Rejected selection is consumed;
  it must not become a delayed action when conditions change.
- `tx_requested`: cumulative messages handed to the CAN publishing path,
  including diagnostics. This is NOT successful wire delivery or lamp count.
- `left_feedback`, `right_feedback`, `trial_lamp_feedback_seen`: vehicle CAN
  feedback; the latter is latched for the current/last accepted trial, including
  acknowledged tests 1/2. It resets on a newly accepted trial.
- `physical_lamp_verified`: always false because this logger cannot see the
  vehicle lamps. Human observation remains separate.
- `restore_ack`, `stock_resumed`: ECU response and stock message recovery.

For the 2023 Ioniq 5, use only acknowledged test 1/2 through `spas_check` after
its live preflight passes. PE-specific trials remain blocked. Keep the test
selector zero between attempts, and stop after an unconfirmed restoration.
No ECU ACK, checksum, counter, timeout, Panda or driver-override guard is relaxed.

### 中文操作順序

1. 更新上述長期測試分支並正常重開機，先保持 SPAS 關閉。
2. 停車 P 檔、退出輔助，執行 `python -m tools.jetlink.spas_check`。
   這一步只讀取，不會發 CAN 指令。
3. 只有預檢通過才開啟「CAN-FD SPAS 方向燈（試驗）」並重開機；
   自動方向燈保持 0，停車測試保持 0。
4. 執行 `python -m tools.jetlink.spas_check --test left`，觀察實體燈，
   同時核對 ECU 接管、車況燈號回饋、恢復確認及 CAN 健康。
5. 左側完成且原廠功能恢復正常後，才另行測右側 `--test right`。
   未亮、被拒絕或恢復未確認就停止，不用小改款專用模式強制發送。
6. 停車成功仍不等於自動方向燈或道路使用已驗收。
