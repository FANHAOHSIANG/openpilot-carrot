<!-- CARROT:GENERATED schema="1" locale="en" group="VEH_CANFD" param="CanfdHDA2" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# CANFD HDA2(0)

**Menu:** Vehicle & Hardware \> CANFD·HDA

---

<!-- CARROT:SETTING:BEGIN CanfdHDA2 -->
<a id="CanfdHDA2"></a>

## CANFD HDA2(0)

`CanfdHDA2`

0: HDA1, 1: HDA2. With CameraSCC at 0, use the stock HDA2 SCC connection; an explicit CameraSCC wiring setting takes precedence. Match the vehicle and harness, then restart after changing.

<!-- CARROT:AUTO:BEGIN CanfdHDA2 -->
<!-- CARROT:AUTO:SOURCE facts="23f0cbfbeeae634664af7d5269c688a9f2def7d20d274b54eb4e15a6b16748d1" semantic="6b24754cbac58c945701508b8f8fc96985d82ba760a595087dd33c95e6210b76" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **Type:** Toggle
- **Default:** `0`
- **Range:** `0` ~ `1`
- **Menu:** Vehicle & Hardware \> CANFD·HDA
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END CanfdHDA2 -->

<!-- CARROT:MANUAL:BEGIN CanfdHDA2 -->
<!-- CARROT:REVIEW reviewed-for="2cd10469d96bc08a71fdfa257929f6cf6790a84cd48e7d2bcc55c07355d65caa" reviewed-at="2026-07-24T16:44:29+09:00" -->
<!-- CARROT:SECTION:BEGIN BEHAVIOR -->
### Behavior

- `0` — Treats a Hyundai/Kia CAN FD vehicle as an HDA1 configuration.
- `1` — Uses the HDA2 CAN-bus configuration.
<!-- CARROT:SECTION:END BEHAVIOR -->

<!-- CARROT:SECTION:BEGIN USAGE -->
### Usage

Confirm the vehicle's HDA and CAN FD configuration, configure while parked, and check the related feature and any faults on the next drive.
<!-- CARROT:SECTION:END USAGE -->

<!-- CARROT:SECTION:BEGIN REFERENCE -->
### Reference

<!-- CARROT:NOTICE level="WARNING" -->
> [!WARNING]
> An unverified CAN FD configuration can cause vehicle warnings or CAN faults.
<!-- CARROT:NOTICE:END -->
<!-- CARROT:SECTION:END REFERENCE -->
<!-- CARROT:MANUAL:END CanfdHDA2 -->

<!-- CARROT:SETTING:END CanfdHDA2 -->
