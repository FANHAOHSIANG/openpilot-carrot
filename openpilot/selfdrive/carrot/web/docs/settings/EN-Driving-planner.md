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
<!-- CARROT:AUTO:SOURCE facts="af7e519dd3ec1363f3ede1f7017ef0d767f5c7d8d63b19baf9bee0423584a17a" semantic="43011f962da56334eea3fa6e6ad3e4475ac3c0b6b8b2ce6aeac2925343af6ae3" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **Type:** Select
- **Default:** CarrotPlanner (`0`)
- **Range:** CarrotPlanner (`0`) ~ Model + following (Sunny) (`4`)
- **Step:** `1`
- **Options:** `0` CarrotPlanner, `1` openpilot Autospeed, `2` Vision-only E2E (experimental), `3` Vision E2E (automatic vehicle setup), `4` Model + following (Sunny)
- **Menu:** Driving \> Cruise & Gap \> Follow Gap
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END DrivingPlannerMode -->

<!-- CARROT:MANUAL:BEGIN DrivingPlannerMode -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END DrivingPlannerMode -->

<!-- CARROT:SETTING:END DrivingPlannerMode -->
