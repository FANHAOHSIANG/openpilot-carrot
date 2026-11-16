<!-- CARROT:GENERATED schema="1" locale="en" group="VEH_CANFD" param="CcncTrafficBackground" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# CCNC cluster traffic-light background

**Menu:** Vehicle & Hardware \> CANFD·HDA

---

<!-- CARROT:SETTING:BEGIN CcncTrafficBackground -->
<a id="CcncTrafficBackground"></a>

## CCNC cluster traffic-light background

`CcncTrafficBackground`

0: Off (default, background as before), 1: On. 0 turns off only this item (for the cluster fixes that always apply see CCNC cluster stock-style display). When openpilot detects a traffic light, changes the CCNC cluster background: red while a red light is detected, green for only 2 s after it turns green. Uses the same detection as the device's traffic-light display (longitudinalPlan.trafficState). The light background takes priority over the cruise and turn backgrounds. - Applies to the same cars as CCNC cluster stock-style display (Hyundai/Kia/Genesis CAN-FD cars on camera SCC with openpilot longitudinal control (HyundaiCameraSCC 1 or 2) once the camera's CCNC cluster frame 0x161 has been received), within about 1 s. - The background values 5 (red) and 8 (green) are not in the DBC; they were checked on an IONIQ 5 PE cluster.

<!-- CARROT:AUTO:BEGIN CcncTrafficBackground -->
<!-- CARROT:AUTO:SOURCE facts="49d22ec245a4d4ee543d757934a4fadb9513a7a8bd0f69579453911fb9ad7c8e" semantic="a384d27d552cb1006f160c4f53c1c2198356bc1f61e0b307e0a7710e03354404" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **Type:** Toggle
- **Default:** `0`
- **Range:** `0` ~ `1`
- **Menu:** Vehicle & Hardware \> CANFD·HDA
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END CcncTrafficBackground -->

<!-- CARROT:MANUAL:BEGIN CcncTrafficBackground -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END CcncTrafficBackground -->

<!-- CARROT:SETTING:END CcncTrafficBackground -->
