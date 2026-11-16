<!-- CARROT:GENERATED schema="1" locale="zh-tw" group="SPEED_CURVE" param="OsmCurveSpeedEnabled" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# 全臺離線 OSM 彎道預覽

**選單:** 駕駛控制 \> 速度與減速 \> 彎道與轉彎

---

<!-- CARROT:SETTING:BEGIN OsmCurveSpeedEnabled -->
<a id="OsmCurveSpeedEnabled"></a>

## 全臺離線 OSM 彎道預覽

`OsmCurveSpeedEnabled`

預設開啟。涵蓋臺灣本島、澎湖、金門、馬祖，停車且連上非計量 Wi-Fi 時自動下載。彎速模式 2/3 生效；無導航路線時，確認定位、方向及近端視覺吻合才提前減速。岔路停止延伸，出彎逐步解除上限。不是導航或自動選路。

<!-- CARROT:AUTO:BEGIN OsmCurveSpeedEnabled -->
<!-- CARROT:AUTO:SOURCE facts="8e2b7856595eb8fe98ef413faecfb91c25f3e763853f1d64364303fc65a6f884" semantic="412daff89b1d6e92d57d1c93016994d460789ef483a1233aa895951023497507" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **型別:** 開關
- **預設值:** `1`
- **範圍:** `0` ~ `1`
- **選單:** 駕駛控制 \> 速度與減速 \> 彎道與轉彎
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END OsmCurveSpeedEnabled -->

<!-- CARROT:MANUAL:BEGIN OsmCurveSpeedEnabled -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END OsmCurveSpeedEnabled -->

<!-- CARROT:SETTING:END OsmCurveSpeedEnabled -->
