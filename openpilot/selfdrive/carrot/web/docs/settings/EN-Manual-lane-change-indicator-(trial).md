<!-- CARROT:GENERATED schema="1" locale="en" group="INDICATOR_AUTO" param="ManualLaneChangeIndicator" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# Manual lane-change indicator (trial)

**Menu:** Vehicle & Hardware \> Indicator Control \> Automatic Indication

---

<!-- CARROT:SETTING:BEGIN ManualLaneChangeIndicator -->
<a id="ManualLaneChangeIndicator"></a>

## Manual lane-change indicator (trial)

`ManualLaneChangeIndicator`

At 5km/h or above, same-direction steering is confirmed for 0.15s. Release or brief countersteer does not erase continued boundary approach: recent intent is retained for up to 1.5s. Approach stopping for over 0.3s, retreat exceeding 0.15m for 0.15s or a four-second episode limit cancels tracking. On the left, fresh OEM white-line classification excludes centre lines; yellow, unknown or stale classifications block requests. On the right, road-edge clearance beyond the approached boundary must be at least 2.5m both nearby and ahead. Outer-line probability, adjacent lane width and road-edge standard deviation are not admission conditions. A wide shoulder can also pass the distance condition. Independent of ATC and the right-turn distance option; never requests automatic steering. Default OFF; Ioniq 5 PE with Jetson USB2CAN and AutoBlinkerControl 1 or 2 only. New requests need three seconds and one second of lamp extinction; steering-feedback isolation remains at least 12 seconds. Detection does not guarantee a real lane or safe gap. Revised behavior needs physical validation. Entry anchors target-line confidence of at least 10%; continuous approach may then be tracked for up to four seconds. After requesting, tracks completion, return or invalid inputs for at most 12 seconds. Immediate extinction of OEM one-touch flashing is not guaranteed. Measured boundary approach projects 0.3 seconds ahead to request indication earlier. The centre-to-boundary distance threshold advances from 0.9m to at most 1.2m; at least 0.15m of actual approach, driver intent and consistent movement of both boundaries remain required. Boundary retreat must persist for 0.15s to cancel tracking, and new indications pause during retreat. Recent steering intent and paired boundary movement with consistent lane width permit bounded position changes during approach. With a continuous target boundary and recent driver intent, a brief jump of the opposite boundary can wait up to 0.15s for valid samples. New indication pauses during the gap and requires consistent movement of both boundaries afterward. The supported Panda/SPAS output uses these same settings and decisions. It is available on IONIQ 5 PE, IONIQ 9 and Azera / Grandeur GN7 with camera-SCC CAN-FD. For manual lane changes and turns, normal completion waits for a minimum of two seconds from the first Panda/SPAS transmission request. Physical lever input, cancellation and input or lane errors end the request immediately. Actual flash count depends on the vehicle.

<!-- CARROT:AUTO:BEGIN ManualLaneChangeIndicator -->
<!-- CARROT:AUTO:SOURCE facts="bb323320d6f5753fcddd3c3aebc496e7ca95da16ab9bce554b6d98f748e29e14" semantic="e186819fff6543b2009f5aa5f2fe8f8cafec3d6e7e48cfdbc02319647576a4d6" review="needs_review" -->
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
