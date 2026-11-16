<!-- CARROT:GENERATED schema="1" locale="zh-tw" group="INDICATOR_LEVER" param="LaneChangeLeverWait" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# 單觸變道請求等待 5 次閃爍

**選單:** 車輛與硬體 \> 轉向燈控制 \> 撥杆操作

---

<!-- CARROT:SETTING:BEGIN LaneChangeLeverWait -->
<a id="LaneChangeLeverWait"></a>

## 單觸變道請求等待 5 次閃爍

`LaneChangeLeverWait`

僅限現代 CAN-FD（0x3C1 撥杆訊號）。單觸撥杆後若變道未立即獲批（BSD、側方車輛、車道線等原有判斷），從撥杆起保持轉向燈並等待 5 次閃爍（約 4 秒）。期間解除則變道，否則放棄請求，剩餘閃爍不會再觸發。鎖定撥杆時照舊持續等待。

<!-- CARROT:AUTO:BEGIN LaneChangeLeverWait -->
<!-- CARROT:AUTO:SOURCE facts="48d6f81a58115121fa931c144be115842f039fbe7ff53992a6b8a79acead72d2" semantic="ea223332818ad995bfa4b772614a0e20f4c64f676f70ec1be8afd5eb871ae2db" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **型別:** 開關
- **預設值:** `0`
- **範圍:** `0` ~ `1`
- **選單:** 車輛與硬體 \> 轉向燈控制 \> 撥杆操作
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END LaneChangeLeverWait -->

<!-- CARROT:MANUAL:BEGIN LaneChangeLeverWait -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:SECTION:BEGIN BEHAVIOR -->
### 運作方式

啟用後，若輕撥變換車道請求被 BSD 或車道檢查阻擋，會保持方向燈及請求約四秒，再加上設定的進入延遲，之後到期。停用時沿用既有依方向燈狀態等待的方式。
<!-- CARROT:SECTION:END BEHAVIOR -->

<!-- CARROT:SECTION:BEGIN USAGE -->
### 使用方式

保持撥桿定位的請求會依既有檢查繼續等待。限時請求到期後，請重新提出請求。
<!-- CARROT:SECTION:END USAGE -->
<!-- CARROT:MANUAL:END LaneChangeLeverWait -->

<!-- CARROT:SETTING:END LaneChangeLeverWait -->
