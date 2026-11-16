<!-- CARROT:GENERATED schema="1" locale="zh-tw" group="VEH_CANFD" param="CcncTrafficBackground" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# CCNC 儀表訊號燈背景

**選單:** 車輛與硬體 \> CANFD·HDA

---

<!-- CARROT:SETTING:BEGIN CcncTrafficBackground -->
<a id="CcncTrafficBackground"></a>

## CCNC 儀表訊號燈背景

`CcncTrafficBackground`

0: 關閉(預設, 背景與以前相同), 1: 開啟。0 只關閉此專案(始終生效的儀表修正見「CCNC 儀表原廠式顯示」)。 openpilot 檢測到訊號燈時改變 CCNC 儀表背景: 檢測到紅燈期間為紅色背景, 變綠後僅2秒為綠色背景。與裝置畫面訊號燈顯示使用相同判斷(longitudinalPlan.trafficState)。訊號燈背景優先於巡航和轉彎背景。 - 適用: 與「CCNC 儀表原廠式顯示」相同的車型(現代·起亞·捷尼賽思 CAN-FD 車型, 攝像頭 SCC 且使用 openpilot 縱向控制(HyundaiCameraSCC 1·2), 並已收到攝像頭的 CCNC 儀表報文 0x161), 約1秒內生效。 - 背景值 5(紅)、8(綠)不在 DBC 中, 已在 IONIQ 5 PE 儀表上確認。

<!-- CARROT:AUTO:BEGIN CcncTrafficBackground -->
<!-- CARROT:AUTO:SOURCE facts="f1beceb409988060112b7eca9973a7c9037af8c3be5d7c70fd3526e1c94b8ca3" semantic="a384d27d552cb1006f160c4f53c1c2198356bc1f61e0b307e0a7710e03354404" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **型別:** 開關
- **預設值:** `0`
- **範圍:** `0` ~ `1`
- **選單:** 車輛與硬體 \> CANFD·HDA
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END CcncTrafficBackground -->

<!-- CARROT:MANUAL:BEGIN CcncTrafficBackground -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END CcncTrafficBackground -->

<!-- CARROT:SETTING:END CcncTrafficBackground -->
