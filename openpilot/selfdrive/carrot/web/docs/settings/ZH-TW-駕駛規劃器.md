<!-- CARROT:GENERATED schema="1" locale="zh-tw" group="CRUISE_GAP" param="DrivingPlannerMode" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# 駕駛規劃器

**選單:** 駕駛控制 \> 巡航與車距 \> 車距

---

<!-- CARROT:SETTING:BEGIN DrivingPlannerMode -->
<a id="DrivingPlannerMode"></a>

## 駕駛規劃器

`DrivingPlannerMode`

下次行程生效。車型自動適配會優先使用車型原本支援的縱向，符合條件時會啟用 Alpha（部分車款會停用原廠 AEB 或雷達），其餘沿用原廠巡航。上游模式使用視覺、跟車與巡航上限決定加速度，並跟隨模型轉向。純視覺模式以鏡頭模型和視覺前車規劃，保留巡航上限；使用原廠巡航時僅提供視覺橫向。

<!-- CARROT:AUTO:BEGIN DrivingPlannerMode -->
<!-- CARROT:AUTO:SOURCE facts="4971bc586bc733c41eb1bb6b8272b8b93e4a25507e1f73c15156cfd3b485eca6" semantic="315a98e2ff21614bb87598630f8bff17e2c46f6243467cb229b50f4c84cd51af" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **型別:** 選擇
- **預設值:** CarrotPlanner (`0`)
- **範圍:** CarrotPlanner (`0`) ~ 純視覺端到端（車型自動適配） (`3`)
- **步長:** `1`
- **選項:** `0` CarrotPlanner, `1` openpilot Autospeed, `2` 純視覺端到端（實驗）, `3` 純視覺端到端（車型自動適配）
- **選單:** 駕駛控制 \> 巡航與車距 \> 車距
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END DrivingPlannerMode -->

<!-- CARROT:MANUAL:BEGIN DrivingPlannerMode -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END DrivingPlannerMode -->

<!-- CARROT:SETTING:END DrivingPlannerMode -->
