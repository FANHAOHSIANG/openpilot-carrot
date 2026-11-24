<!-- CARROT:GENERATED schema="1" locale="en" group="CRUISE_GAP" param="DrivingPlannerMode" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# Driving planner

**Menu:** Driving \> Cruise & Gap \> Follow Gap

---

<!-- CARROT:SETTING:BEGIN DrivingPlannerMode -->
<a id="DrivingPlannerMode"></a>

## Driving planner

`DrivingPlannerMode`

Applies on the next drive. Automatic setup may enable Alpha longitudinal, which disables stock AEB or radar on some vehicles. Other vehicles retain stock cruise.

<!-- CARROT:AUTO:BEGIN DrivingPlannerMode -->
<!-- CARROT:AUTO:SOURCE facts="591eb2e67a4b0f2ff440a16daf4797a04ae33b9bf9c1d5815896474f31fa6b4d" semantic="315a98e2ff21614bb87598630f8bff17e2c46f6243467cb229b50f4c84cd51af" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **Type:** Select
- **Default:** CarrotPlanner (`0`)
- **Range:** CarrotPlanner (`0`) ~ Vision E2E (automatic vehicle setup) (`3`)
- **Step:** `1`
- **Options:** `0` CarrotPlanner, `1` openpilot Autospeed, `2` Vision-only E2E (experimental), `3` Vision E2E (automatic vehicle setup)
- **Menu:** Driving \> Cruise & Gap \> Follow Gap
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END DrivingPlannerMode -->

<!-- CARROT:MANUAL:BEGIN DrivingPlannerMode -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END DrivingPlannerMode -->

<!-- CARROT:SETTING:END DrivingPlannerMode -->
