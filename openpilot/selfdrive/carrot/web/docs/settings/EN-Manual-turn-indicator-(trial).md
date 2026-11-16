<!-- CARROT:GENERATED schema="1" locale="en" group="INDICATOR_AUTO" param="ManualTurnIndicator" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# Manual turn indicator (trial)

**Menu:** Vehicle & Hardware \> Indicator Control \> Automatic Indication

---

<!-- CARROT:SETTING:BEGIN ManualTurnIndicator -->
<a id="ManualTurnIndicator"></a>

## Manual turn indicator (trial)

`ManualTurnIndicator`

Detects driver turns using steering torque, wheel movement and measured vehicle rotation. Operates independently of ATC, including intersections with faint lane markings. Starts at 5–60km/h after 0.15s same-direction driver torque, at least 42 degrees steering with a 22-degree increase and consistent vehicle rotation. Ends after wheel return within ±15 degrees and settled rotation, opposite driver steering, or 30 seconds. Default OFF. Requires Ioniq 5 PE, a supported indicator adapter and AutoBlinkerControl 1 or 2. Parking-aisle turns can also trigger. Curves and evasive maneuvers can cause false indications. Physical lamp validation remains pending. When same-direction manual-turn conditions are met during a manual lane indication, the existing request continues under turn completion tracking. Lane-position jumps at junctions do not reset manual turns established through driver torque, increasing steering angle and measured rotation. An owned indication survives small negative speed-estimator noise around zero while standstill is confirmed in Drive. The supported Panda/SPAS output uses these same settings and decisions. It is available on IONIQ 5 PE, IONIQ 9 and Azera / Grandeur GN7 with camera-SCC CAN-FD. For manual lane changes and turns, normal completion waits for a minimum of two seconds from the first Panda/SPAS transmission request. Physical lever input, cancellation and input or lane errors end the request immediately. Actual flash count depends on the vehicle.

<!-- CARROT:AUTO:BEGIN ManualTurnIndicator -->
<!-- CARROT:AUTO:SOURCE facts="573504295612a1308b15b5dc1c8aa6fbe1426897e4bb5f8d38580d8c7db10ca2" semantic="e4bbf6a833570ad6bb05e5eb7b686cd71385572d1c15c465dd90e155a3b801b4" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **Type:** Toggle
- **Default:** `0`
- **Range:** `0` ~ `1`
- **Menu:** Vehicle & Hardware \> Indicator Control \> Automatic Indication
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END ManualTurnIndicator -->

<!-- CARROT:MANUAL:BEGIN ManualTurnIndicator -->
<!-- CARROT:REVIEW reviewed-for="e08aa7e7e006ddb909a0060571a3f7983d6c70f1249f7f29cc42c19e87f3451a" reviewed-at="2026-11-14T02:05:14Z" -->
<!-- CARROT:SECTION:BEGIN BEHAVIOR -->
### Behavior

Combines same-direction driver torque, increasing wheel angle and fresh measured vehicle rotation to indicate a turn. Works independently of ATC and lateral-control activation, with lamp feedback isolated from automatic steering requests.

Wheel return and settled rotation complete the request. Opposite driver steering, invalid inputs or disabling the setting end it.
A new manual turn requires two seconds since the previous indication last renewed its hold and one continuous second with both lamps off. These intervals run concurrently.
If same-direction manual-turn conditions are met during a manual lane indication, the existing request and acknowledgement continue under turn-completion tracking; this is not a new tap request.
<!-- CARROT:SECTION:END BEHAVIOR -->

<!-- CARROT:SECTION:BEGIN USAGE -->
### Usage

After Git Pull, restart comma and enable this option. Requires Ioniq 5 PE with a supported indicator adapter and AutoBlinkerControl 1 or 2.
<!-- CARROT:SECTION:END USAGE -->

<!-- CARROT:SECTION:BEGIN REFERENCE -->
### Reference

Parking aisles, ramps and parking entry can also trigger. Unmarked bends and evasive movements can produce false indications. Physical lamp validation remains pending.

[Detailed conditions](https://github.com/ajouatom/openpilot/blob/carrot-wip/docs/user/en/lane-change.md)
<!-- CARROT:SECTION:END REFERENCE -->

<!-- CARROT:MANUAL:END ManualTurnIndicator -->

<!-- CARROT:SETTING:END ManualTurnIndicator -->
