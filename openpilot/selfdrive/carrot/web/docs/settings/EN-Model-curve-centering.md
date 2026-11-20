<!-- CARROT:GENERATED schema="1" locale="en" group="STEER_LANEMODE" param="ModelCurveCentering" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# Model curve centering

**Menu:** Driving \> Steering \> Lane Mode

---

<!-- CARROT:SETTING:BEGIN ModelCurveCentering -->
<a id="ModelCurveCentering"></a>

## Model curve centering

`ModelCurveCentering`

On the CAN-FD IONIQ 5, gently correct the steering target toward lane center when laneless model steering predicts a path too close to the inside of a curve and both lane lines are reliable. Off by default.

<!-- CARROT:AUTO:BEGIN ModelCurveCentering -->
<!-- CARROT:AUTO:SOURCE facts="9dae7358ca6b4c956792894ccb32ffda502df2ef08b64ba10a5d280606ad1a54" semantic="93bb71bdc261b9cd8a21ddbe3c2243f790b32d7b9141d440191bda6e9e442b20" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **Type:** Toggle
- **Default:** `0`
- **Range:** `0` ~ `1`
- **Menu:** Driving \> Steering \> Lane Mode
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END ModelCurveCentering -->

<!-- CARROT:MANUAL:BEGIN ModelCurveCentering -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END ModelCurveCentering -->

<!-- CARROT:SETTING:END ModelCurveCentering -->
