<!-- CARROT:GENERATED schema="1" locale="zh" group="SPEED_CURVE" param="MapTurnSpeedFactor" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# 地图转向速度因子

**菜单:** 驾驶控制 \> 速度与减速 \> 弯道与转弯

---

<!-- CARROT:SETTING:BEGIN MapTurnSpeedFactor -->
<a id="MapTurnSpeedFactor"></a>

## 地图转向速度因子

`MapTurnSpeedFactor`

匹配路线的弯道目标速度比例。数值越小减速越多，在按距离计算进弯速度前应用。

<!-- CARROT:AUTO:BEGIN MapTurnSpeedFactor -->
<!-- CARROT:AUTO:SOURCE facts="76c616d124f720f8fef70f48b3216edcd568f1e2254b85c35f4acc8ef3687fbf" semantic="0ff206783eb8d00f1c12b1e6af36b0ad3bedfa9fc1b77780eb6b53c6dd0577e5" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **类型:** 数值
- **默认值:** `100%`
- **范围:** `50%` ~ `300%`
- **步长:** `10`
- **显示单位:** `%`
- **菜单:** 驾驶控制 \> 速度与减速 \> 弯道与转弯
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END MapTurnSpeedFactor -->

<!-- CARROT:MANUAL:BEGIN MapTurnSpeedFactor -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END MapTurnSpeedFactor -->

<!-- CARROT:SETTING:END MapTurnSpeedFactor -->
