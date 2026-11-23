<!-- CARROT:GENERATED schema="1" locale="en" group="INDICATOR_OUTPUT" param="CanfdBlinkerKickMode" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# Panda/SPAS Send Mode

**Menu:** Vehicle & Hardware \> Indicator Control \> Output Device

---

<!-- CARROT:SETTING:BEGIN CanfdBlinkerKickMode -->
<a id="CanfdBlinkerKickMode"></a>

## Panda/SPAS Send Mode

`CanfdBlinkerKickMode`

How Panda/SPAS Indicator Output sends its blinker command. Default 1. 0: only after the parking ECU answers the pause request and its stock SPAS frames stop; no answer, no lamp (the IONIQ 5 PE did not answer). 1: piggyback. If the ECU does not answer, panda sends our SPAS frame right behind each stock SPAS frame, so the same id never starts at the same moment and does not collide. If the ECU answers, same as 0. - Cars and wiring: the same as Panda/SPAS Indicator Output. In mode 1, a confirmed unanswered probe can be reused for 60 seconds from that probe while stock SPAS reception and output ownership remain healthy, avoiding another 0.4s reply wait on the next request. Interrupted reception, a new ECU reply, lost ownership, changed settings or expiry require another probe. Mode 0 still requires an ECU reply; stock-frame synchronization and driver cancellation remain.

<!-- CARROT:AUTO:BEGIN CanfdBlinkerKickMode -->
<!-- CARROT:AUTO:SOURCE facts="fd5bac59a604845a5efd8ad40109d167bae831e3cb4164b4b457ec78b98352e2" semantic="70568faca97452808ebd34cfcdcab63fc7b42577cc2420a1aeaf4adf8e066b41" review="needs_review" -->
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
