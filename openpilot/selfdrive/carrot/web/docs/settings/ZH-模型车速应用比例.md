<!-- CARROT:GENERATED schema="1" locale="zh" group="SPEED_CURVE" param="ApplyModelSpeed" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# 模型车速应用比例

**菜单:** 驾驶控制 \> 速度与减速 \> 弯道与转弯

---

<!-- CARROT:SETTING:BEGIN ApplyModelSpeed -->
<a id="ApplyModelSpeed"></a>

## 模型车速应用比例

`ApplyModelSpeed`

本测试分支的自动模型速度不得超过已设定巡航速度。负值可降低目标；正值的自动提速会被阻止。

<!-- CARROT:AUTO:BEGIN ApplyModelSpeed -->
<!-- CARROT:AUTO:SOURCE facts="8272357f23ac69a9185340ac5bb52a5405b7ee3771d4d31f26fa3dc33c2f3db7" semantic="af76e5561f6e0bbefc54c91f7b945aab79d8f017c8706ca26a324cbcc31a3514" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **类型:** 数值
- **默认值:** `0%`
- **范围:** `-120%` ~ `120%`
- **步长:** `1`
- **显示单位:** `%`
- **菜单:** 驾驶控制 \> 速度与减速 \> 弯道与转弯
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END ApplyModelSpeed -->

<!-- CARROT:MANUAL:BEGIN ApplyModelSpeed -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END ApplyModelSpeed -->

<!-- CARROT:SETTING:END ApplyModelSpeed -->
