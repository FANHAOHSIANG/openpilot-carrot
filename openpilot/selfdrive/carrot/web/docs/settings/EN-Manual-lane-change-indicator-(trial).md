<!-- CARROT:GENERATED schema="1" locale="en" group="INDICATOR_AUTO" param="ManualLaneChangeIndicator" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# Manual lane-change indicator (trial)

**Menu:** Vehicle & Hardware \> Indicator Control \> Automatic Indication

---

<!-- CARROT:SETTING:BEGIN ManualLaneChangeIndicator -->
<a id="ManualLaneChangeIndicator"></a>

## Manual lane-change indicator (trial)

`ManualLaneChangeIndicator`

Manual lane-change indication no longer excludes OEM left marking colours or centre-line classifications, or right road-edge clearance. The 5km/h minimum, driver intent, measured boundary approach, valid lane width, continuity and recent target-line confidence remain required. It never requests automatic steering. After a boundary attempt ends within two seconds, an independently confirmed same-side manual turn can create a new request; a fresh opposite boundary approach can rearm after one continuous dark second. Driver lever, opposite lamps, invalid inputs and cancellation retain priority; steering-feedback isolation remains. Centre-line approaches and movements beyond the road can also indicate.

<!-- CARROT:AUTO:BEGIN ManualLaneChangeIndicator -->
<!-- CARROT:AUTO:SOURCE facts="4cf88a403568c59110846b5d0822df31b48a2f17534e671d11b0f9b3a161eb92" semantic="b054132b7f6fb71e55d9758b1d6cdc54cb75fac679420524d7691e6c8c56817a" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **Type:** Toggle
- **Default:** `0`
- **Range:** `0` ~ `1`
- **Menu:** Vehicle & Hardware \> Indicator Control \> Automatic Indication
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END ManualLaneChangeIndicator -->

<!-- CARROT:MANUAL:BEGIN ManualLaneChangeIndicator -->
<!-- CARROT:REVIEW reviewed-for="d96432b8f8ff840459f65cab076ba12f6d57b1d333e585a4be25652182e1e7ba" reviewed-at="2026-11-14T02:05:14Z" -->
<!-- CARROT:SECTION:BEGIN BEHAVIOR -->
### Behavior

Indicates recent driver intent with continuous boundary approach. Entry anchors target-line confidence of at least 10% and applies left centre-line and right road-edge exclusions.

After a request it tracks completion, return and invalid inputs without requesting automatic steering. OEM one-touch flashing may remain after the hold ends.
Measured boundary approach projects 0.3 seconds ahead to request indication earlier. The centre-to-boundary distance threshold advances from 0.9m to at most 1.2m; at least 0.15m of actual approach, driver intent and consistent movement of both boundaries remain required.

Manual/model indication distinguishes its short one-touch echo only with matching request time, direction and stalk counters. Opposite input, a latched lever or receiver-detected driver intervention cancels. Lamp feedback preceding the completed-send response is remembered briefly; holding still requires the matching response. Same-direction physical input during the brief transmission interval cannot be uniquely distinguished from these fields alone.
From 5 km/h, manual steering and measured approach to an adjacent lane can trigger the corresponding indicator.
Boundary retreat must persist for 0.15 seconds before cancelling an approach; new indications pause during retreat. Recent driver intent and paired boundary movement with consistent lane width allow bounded position changes during the approach.

With B1 release 5, a confirmed own-tap echo can remain accepted through dark flash intervals. Neutral feedback after the tap closes that allowance; a later lever report cancels ownership. Opposite lamps, raw driver input, invalid CAN and expired leases still cancel. Software replay does not establish physical hold or cancellation performance.
<!-- CARROT:SECTION:END BEHAVIOR -->
<!-- CARROT:MANUAL:END ManualLaneChangeIndicator -->

<!-- CARROT:SETTING:END ManualLaneChangeIndicator -->
