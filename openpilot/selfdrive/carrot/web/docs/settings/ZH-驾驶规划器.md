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
<!-- CARROT:AUTO:SOURCE facts="b762740ea3a30efd5a66d29839e81a5af6e74ecdd233e2925182f1da4d401a4a" semantic="315a98e2ff21614bb87598630f8bff17e2c46f6243467cb229b50f4c84cd51af" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **类型:** 选择
- **默认值:** CarrotPlanner (`0`)
- **范围:** CarrotPlanner (`0`) ~ 纯视觉端到端（车型自动适配） (`3`)
- **步长:** `1`
- **选项:** `0` CarrotPlanner, `1` openpilot Autospeed, `2` 纯视觉端到端（实验）, `3` 纯视觉端到端（车型自动适配）
- **菜单:** 驾驶控制 \> 巡航与车距 \> 车距
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END DrivingPlannerMode -->

<!-- CARROT:MANUAL:BEGIN DrivingPlannerMode -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END DrivingPlannerMode -->

<!-- CARROT:SETTING:END DrivingPlannerMode -->
