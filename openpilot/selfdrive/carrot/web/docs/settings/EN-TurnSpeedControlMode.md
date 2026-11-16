<!-- CARROT:GENERATED schema="1" locale="en" group="SPEED_CURVE" param="TurnSpeedControlMode" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# TurnSpeedControlMode

**Menu:** Driving \> Speed & Decel \> Curve & Turn

---

<!-- CARROT:SETTING:BEGIN TurnSpeedControlMode -->
<a id="TurnSpeedControlMode"></a>

## TurnSpeedControlMode

`TurnSpeedControlMode`

0: off, 1: vision, 2: vision + matched route, 3: matched route

<!-- CARROT:AUTO:BEGIN TurnSpeedControlMode -->
<!-- CARROT:AUTO:SOURCE facts="df18bc65022efc9abf31fdbe12e0d0c0a9d29f222b1933c5591afba9bcf92a6b" semantic="db2399ff8f834bd37741fa4c0751142f9ca87ceeeb55df6ad1bc86a9828f8ec6" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **Type:** Segmented choice
- **Default:** `1`
- **Range:** `0` ~ `3`
- **Step:** `1`
- **Menu:** Driving \> Speed & Decel \> Curve & Turn
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END TurnSpeedControlMode -->

<!-- CARROT:MANUAL:BEGIN TurnSpeedControlMode -->
<!-- CARROT:REVIEW reviewed-for="0e0a5e58e9061594b9a41986ec433b7b6680c5f6ce99da897cd9b4e52ded8e38" reviewed-at="2026-07-24T16:44:29+09:00" -->
<!-- CARROT:SECTION:BEGIN BEHAVIOR -->
### Behavior

The selected value changes behavior as follows.

- `0` — not use
- `1` — vision
- `2` — vision+route
- `3` — route(always)
<!-- CARROT:SECTION:END BEHAVIOR -->

<!-- CARROT:SECTION:BEGIN USAGE -->
### Usage

Adjust one item at a time on the same curve and route-guidance condition, comparing the target before entry and the speed through the curve.
<!-- CARROT:SECTION:END USAGE -->

<!-- CARROT:SECTION:BEGIN REFERENCE -->
### Reference

[Related user guide](https://github.com/ajouatom/openpilot/blob/carrot-wip/docs/user/en/speed-deceleration.md)
<!-- CARROT:SECTION:END REFERENCE -->
<!-- CARROT:MANUAL:END TurnSpeedControlMode -->

<!-- CARROT:SETTING:END TurnSpeedControlMode -->
