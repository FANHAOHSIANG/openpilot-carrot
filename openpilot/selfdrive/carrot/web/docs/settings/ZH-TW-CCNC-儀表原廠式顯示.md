<!-- CARROT:GENERATED schema="1" locale="zh-tw" group="VEH_CANFD" param="CcncClusterDisplay" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# CCNC 儀表原廠式顯示

**選單:** 車輛與硬體 \> CANFD·HDA

---

<!-- CARROT:SETTING:BEGIN CcncClusterDisplay -->
<a id="CcncClusterDisplay"></a>

## CCNC 儀表原廠式顯示

`CcncClusterDisplay`

0: 關閉(預設), 1: 開啟。0 只關閉下列專案; HDP 車距顯示·彈窗、側方方框→灰色車輛、停車時轉向圖示的修正與此設定無關, 始終生效。 適用: 現代·起亞·捷尼賽思 CAN-FD 車型, 攝像頭 SCC 且使用 openpilot 縱向控制(HyundaiCameraSCC 1·2), 並已收到攝像頭的 CCNC 儀表報文 0x161(HDP 圖示需 0x162)。openpilot 修改並重新傳送這些報文, 像原廠 HDA2 一樣在儀表上顯示 openpilot 狀態。約1秒內生效。 - 車道線: 模型車道線機率持續1秒以上低於0.08且攝像頭也看不到時不顯示該線(達到0.12再顯示, 橙色線保留)。IONIQ 9、EV9 保持原有車道線顯示。 - 虛線: 攝像頭識別為虛線的車道線顯示為虛線(IONIQ 5 PE、Grandeur GN7、EV4)。 - 車道高亮: 轉向工作時按狀態改變車道顏色。無車道模式綠色、車道模式天藍色、轉向角誤差持續0.3秒黃色、轉向極限紅色、變道中綠色。有隱藏車道線時不改變。 - 前車圓環: 前車可見時, 巡航中藍色圓環位於 openpilot 保持的目標車距, 非巡航時顯示白色圓環。 - 彈窗: 巡航開啟或解除時顯示原廠提示彈窗2秒。 - 警告文字: 部分 openpilot 警告(車速過高、轉向/SCC 不可用、轉向極限、CAN/感測器異常)顯示為原廠文字。轉向極限(注意周圍)文字同時像原廠一樣發出1秒雙響提示音。DBC 未列出的文字僅在 IONIQ 5 PE、Grandeur GN7、EV4 上顯示。 - HDP 圖示: 巡航或轉向工作時點亮 HDP 圖示(IONIQ 5 PE、Grandeur GN7、EV4)。

<!-- CARROT:AUTO:BEGIN CcncClusterDisplay -->
<!-- CARROT:AUTO:SOURCE facts="1f0cba11db240626eb2c609a29c308c442dd2232b29ed5a59a6e6c90185789b7" semantic="51f05ac1b11c155f7bc0190c1fc950a3b08c18761a77b6a68f9ed9e16b394137" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **型別:** 開關
- **預設值:** `0`
- **範圍:** `0` ~ `1`
- **選單:** 車輛與硬體 \> CANFD·HDA
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END CcncClusterDisplay -->

<!-- CARROT:MANUAL:BEGIN CcncClusterDisplay -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END CcncClusterDisplay -->

<!-- CARROT:SETTING:END CcncClusterDisplay -->
