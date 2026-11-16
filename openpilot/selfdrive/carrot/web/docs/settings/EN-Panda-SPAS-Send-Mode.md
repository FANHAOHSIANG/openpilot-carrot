<!-- CARROT:GENERATED schema="1" locale="en" group="INDICATOR_OUTPUT" param="CanfdBlinkerKickMode" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# Panda/SPAS Send Mode

**Menu:** Vehicle & Hardware \> Indicator Control \> Output Device

---

<!-- CARROT:SETTING:BEGIN CanfdBlinkerKickMode -->
<a id="CanfdBlinkerKickMode"></a>

## Panda/SPAS Send Mode

`CanfdBlinkerKickMode`

How Panda/SPAS Indicator Output sends its blinker command. Default 1. 0: only after the parking ECU answers the pause request and its stock SPAS frames stop; no answer, no lamp (the IONIQ 5 PE did not answer). 1: piggyback. If the ECU does not answer, panda sends our SPAS frame right behind each stock SPAS frame, so the same id never starts at the same moment and does not collide. If the ECU answers, same as 0. - Cars and wiring: the same as Panda/SPAS Indicator Output.

<!-- CARROT:AUTO:BEGIN CanfdBlinkerKickMode -->
<!-- CARROT:AUTO:SOURCE facts="13a97cf907746b6810ff06bda16f6edbf052337b5444700daf795351eab63289" semantic="50e1f21152cd48de144012c02d1efe05b4cc7b29ef1a56a4eaec16e1fb980935" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **Type:** Toggle
- **Default:** `1`
- **Range:** `0` ~ `1`
- **Menu:** Vehicle & Hardware \> Indicator Control \> Output Device
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END CanfdBlinkerKickMode -->

<!-- CARROT:MANUAL:BEGIN CanfdBlinkerKickMode -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END CanfdBlinkerKickMode -->

<!-- CARROT:SETTING:END CanfdBlinkerKickMode -->
