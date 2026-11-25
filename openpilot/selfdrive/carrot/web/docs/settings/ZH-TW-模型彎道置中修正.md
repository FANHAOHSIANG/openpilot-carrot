<!-- CARROT:GENERATED schema="1" locale="zh-tw" group="STEER_LANEMODE" param="ModelCurveCentering" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# 模型彎道置中修正

**選單:** 駕駛控制 \> 轉向 \> 車道模式

---

<!-- CARROT:SETTING:BEGIN ModelCurveCentering -->
<a id="ModelCurveCentering"></a>

## 模型彎道置中修正

`ModelCurveCentering`

僅適用於 CAN-FD IONIQ 5。使用純模型轉向時，若兩側車道線可信且預測路徑偏向彎道內側，就朝車道中央微調轉向目標。預設關閉。

<!-- CARROT:AUTO:BEGIN ModelCurveCentering -->
<!-- CARROT:AUTO:SOURCE facts="b54c5780345542ce5cc5ef9d8c7d01fc4169dc177a1e6608a2251d484fdea134" semantic="93bb71bdc261b9cd8a21ddbe3c2243f790b32d7b9141d440191bda6e9e442b20" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **型別:** 開關
- **預設值:** `0`
- **範圍:** `0` ~ `1`
- **選單:** 駕駛控制 \> 轉向 \> 車道模式
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END ModelCurveCentering -->

<!-- CARROT:MANUAL:BEGIN ModelCurveCentering -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END ModelCurveCentering -->

<!-- CARROT:SETTING:END ModelCurveCentering -->
