<!-- CARROT:GENERATED schema="1" locale="en" group="SPEED_LIMIT" param="AutoRoadSpeedAdjust" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# AutoRoadLimitSpeedAdjust (50)%

**Menu:** Driving \> Speed & Decel \> Speed Limit

---

<!-- CARROT:SETTING:BEGIN AutoRoadSpeedAdjust -->
<a id="AutoRoadSpeedAdjust"></a>

## AutoRoadLimitSpeedAdjust (50)%

`AutoRoadSpeedAdjust`

Automatic road adjustment cannot raise set speed. -1: sync to a lower road target; 0: keep; 50: weighted decrease; 100: lower new limit.

<!-- CARROT:AUTO:BEGIN AutoRoadSpeedAdjust -->
<!-- CARROT:AUTO:SOURCE facts="ddc71e4a0694e1d6e45fa5c34e11dd4124d8397128a4f2efcfabeff1f0dd2fc9" semantic="3a8ce492ec99592a4b2c648c4396de135f8541b50514f8cf9b5673d419e3bbf9" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **Type:** Number
- **Default:** `0%`
- **Range:** `-1%` ~ `100%`
- **Step:** `10`
- **Display unit:** `%`
- **Menu:** Driving \> Speed & Decel \> Speed Limit
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END AutoRoadSpeedAdjust -->

<!-- CARROT:MANUAL:BEGIN AutoRoadSpeedAdjust -->
<!-- CARROT:REVIEW reviewed-for="c5639d7240a075f5e1e1594a87177824bc3d8bf0192fbf8b3dc2b51a26ea762a" reviewed-at="2026-07-24T16:44:29+09:00" -->
<!-- CARROT:SECTION:BEGIN BEHAVIOR -->
### Behavior

- `-1` — Immediately follows the new road-limit-based target when the road speed limit changes.
- `0` — Keeps the existing cruise set speed.
- `1`–`99` — Blends the existing set speed with a newly reduced road limit; higher values move closer to the new limit.
- `100` — Applies the newly reduced road limit directly.
<!-- CARROT:SECTION:END BEHAVIOR -->

<!-- CARROT:SECTION:BEGIN USAGE -->
### Usage

Check the new target speed and transition timing on the same section where the road speed limit changes.
<!-- CARROT:SECTION:END USAGE -->

<!-- CARROT:SECTION:BEGIN REFERENCE -->
### Reference

[Related user guide](https://github.com/ajouatom/openpilot/blob/carrot-wip/docs/user/en/speed-deceleration.md)
<!-- CARROT:SECTION:END REFERENCE -->
<!-- CARROT:MANUAL:END AutoRoadSpeedAdjust -->

<!-- CARROT:SETTING:END AutoRoadSpeedAdjust -->
