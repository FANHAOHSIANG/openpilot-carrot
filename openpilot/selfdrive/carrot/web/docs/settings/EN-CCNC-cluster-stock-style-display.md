<!-- CARROT:GENERATED schema="1" locale="en" group="VEH_CANFD" param="CcncClusterDisplay" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# CCNC cluster stock-style display

**Menu:** Vehicle & Hardware \> CANFD·HDA

---

<!-- CARROT:SETTING:BEGIN CcncClusterDisplay -->
<a id="CcncClusterDisplay"></a>

## CCNC cluster stock-style display

`CcncClusterDisplay`

0: Off (default), 1: On. 0 turns off only the items below; the HDP gap display / popup, side box -\> grey car and standstill steering icon fixes always apply, whatever this is set to. Applies to Hyundai/Kia/Genesis CAN-FD cars on camera SCC with openpilot longitudinal control (HyundaiCameraSCC 1 or 2) once the camera's CCNC cluster frame 0x161 (0x162 for the HDP icon) has been received. openpilot re-sends those frames and shows its state on the cluster the way the stock HDA2 display does. Applies within about 1 s. - Lane lines: a line whose model probability stays under 0.08 for over 1 s and that the camera does not see either is not drawn (drawn again from 0.12; an orange line stays). IONIQ 9 / EV9 keep the previous lane display. - Dashed: a line the camera reports as dashed is drawn dashed (IONIQ 5 PE, Azera / Grandeur GN7 and EV4). - Lane highlight by steering state while steering: laneless green, lane mode sky blue, steering angle error for 0.3 s yellow, steering limit red, green during a lane change. Not changed while a lane line is hidden. - Lead ring on a visible lead: blue at the gap openpilot keeps while cruising, white when not cruising. - Popups: the stock popup for 2 s when cruise is engaged or released. - Alert texts: some openpilot alerts (speed too high, steering / SCC unavailable, steering limit, CAN / sensor faults) show as stock texts. The steering-limit text (check surroundings) also plays the stock double chime for 1 s. Texts that the DBC does not list show only on the IONIQ 5 PE, Azera / Grandeur GN7 and EV4. - HDP icon while cruise or steering is active (IONIQ 5 PE, Azera / Grandeur GN7 and EV4).

<!-- CARROT:AUTO:BEGIN CcncClusterDisplay -->
<!-- CARROT:AUTO:SOURCE facts="df9036aa30f1dce780b3a805bea9534d3335ba8bcc0ac9d98d3e4fb60ec77268" semantic="51f05ac1b11c155f7bc0190c1fc950a3b08c18761a77b6a68f9ed9e16b394137" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **Type:** Toggle
- **Default:** `0`
- **Range:** `0` ~ `1`
- **Menu:** Vehicle & Hardware \> CANFD·HDA
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END CcncClusterDisplay -->

<!-- CARROT:MANUAL:BEGIN CcncClusterDisplay -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END CcncClusterDisplay -->

<!-- CARROT:SETTING:END CcncClusterDisplay -->
