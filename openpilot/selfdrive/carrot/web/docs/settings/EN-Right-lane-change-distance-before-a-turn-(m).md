<!-- CARROT:GENERATED schema="1" locale="en" group="STEER_LANECHANGE" param="AutoTurnControlRightLaneChange" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# Right lane-change distance before a turn (m)

**Menu:** Driving \> Steering \> Lane Change (Auto Turn)

---

<!-- CARROT:SETTING:BEGIN AutoTurnControlRightLaneChange -->
<a id="AutoTurnControlRightLaneChange"></a>

## Right lane-change distance before a turn (m)

`AutoTurnControlRightLaneChange`

Zero metres disables the add-on; the maximum setting is 2000m. Fresh, explicit motorway/expressway navigation uses the selected distance. Other roads, unknown or expired road information use the smaller of the setting and 500m. Selecting 2000m gives 500m on local roads and 2000m on highways. Lane count alone does not identify a highway. Existing stored values are preserved. The former ON setting migrates to 250m at startup. Adds to existing ATC modes 1 and 2. At 10km/h or above and within the configured distance of a TBT right turn or right fork, requests the right indicator until the turn starts. Requires the protocol-matched USB2CAN, BLE or Panda/SPAS setup, AutoBlinkerControl=2 and LaneChangeNeedTorque=0. Rear admission uses fresh OEM BSD warnings only, without corner distances. Every detected right-lane front target must be at least 5m away now and after a three-second constant-relative-speed projection. Radar errors or stale input block initiation. Steering before a request resets confirmation; driver intervention after a request cancels it. Signals started below 30km/h remain indication-only until they end; only starts at or above 30km/h enter ordinary lane-change handling. Requires at least 2.5m beyond the right boundary to the road edge. Native Kick also passes the physical lamp of an admitted ATC request started at or above 30km/h to ordinary lane-change admission. Display-only signals and remaining flashes after cancellation stay excluded from automatic steering. The four-second start wait and existing cancellation conditions remain; no minimum flash count is guaranteed.

<!-- CARROT:AUTO:BEGIN AutoTurnControlRightLaneChange -->
<!-- CARROT:AUTO:SOURCE facts="ce3f2ae3b8def12c28ede29068cd600c06c36739c6a300c342fc05019a7c79cc" semantic="c7837f43c48a0b5200b4346241f2335323cffcce3eff5cbf9e02db29380b7032" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **Type:** Number
- **Default:** `0`
- **Range:** `0` ~ `2000`
- **Step:** `50`
- **Menu:** Driving \> Steering \> Lane Change (Auto Turn)
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END AutoTurnControlRightLaneChange -->

<!-- CARROT:MANUAL:BEGIN AutoTurnControlRightLaneChange -->
<!-- CARROT:REVIEW reviewed-for="3008498ad9b26c4e6721da72acaa56057939a66d7d15c51954adbc9bb64b1584" reviewed-at="2026-11-02T22:15:29.514979+00:00" -->
<!-- CARROT:SECTION:BEGIN BEHAVIOR -->
### Behavior

Zero metres disables the add-on. Higher values check conditions farther before a right turn or fork. A value of 250m uses the former range, and the former ON setting migrates to 250m at restart.

At 10km/h or above, checks the right lane/edge, valid BSD and current/projected three-second front gaps. Signals started below 30km/h remain indication-only, while starts at or above 30km/h enter ordinary lane-change handling.
<!-- CARROT:SECTION:END BEHAVIOR -->
<!-- CARROT:MANUAL:END AutoTurnControlRightLaneChange -->

<!-- CARROT:SETTING:END AutoTurnControlRightLaneChange -->
