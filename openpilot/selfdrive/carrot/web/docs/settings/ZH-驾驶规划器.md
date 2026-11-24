<!-- CARROT:GENERATED schema="1" locale="zh" group="CRUISE_GAP" param="DrivingPlannerMode" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# 驾驶规划器

**菜单:** 驾驶控制 \> 巡航与车距 \> 车距

---

<!-- CARROT:SETTING:BEGIN DrivingPlannerMode -->
<a id="DrivingPlannerMode"></a>

## 驾驶规划器

`DrivingPlannerMode`

下次行程生效。自动适配可能启用 Alpha，部分车型会停用原厂 AEB 或雷达。

<!-- CARROT:AUTO:BEGIN DrivingPlannerMode -->
<!-- CARROT:AUTO:SOURCE facts="d7989d1f6d819e92f4e9b367ef5616b93ddd0c45d406e2f09ca280dbc4ed712d" semantic="43011f962da56334eea3fa6e6ad3e4475ac3c0b6b8b2ce6aeac2925343af6ae3" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **类型:** 选择
- **默认值:** CarrotPlanner (`0`)
- **范围:** CarrotPlanner (`0`) ~ 模型与跟车协同（Sunny） (`4`)
- **步长:** `1`
- **选项:** `0` CarrotPlanner, `1` openpilot Autospeed, `2` 纯视觉端到端（实验）, `3` 纯视觉端到端（车型自动适配）, `4` 模型与跟车协同（Sunny）
- **菜单:** 驾驶控制 \> 巡航与车距 \> 车距
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END DrivingPlannerMode -->

<!-- CARROT:MANUAL:BEGIN DrivingPlannerMode -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END DrivingPlannerMode -->

<!-- CARROT:SETTING:END DrivingPlannerMode -->
