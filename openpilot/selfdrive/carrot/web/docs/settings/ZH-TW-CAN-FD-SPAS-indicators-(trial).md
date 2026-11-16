<!-- CARROT:GENERATED schema="1" locale="zh-tw" group="INDICATOR_OUTPUT" param="CanfdBlinkerControl" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# CAN-FD SPAS indicators (trial)

**選單:** 車輛與硬體 \> 轉向燈控制 \> 輸出裝置

---

<!-- CARROT:SETTING:BEGIN CanfdBlinkerControl -->
<a id="CanfdBlinkerControl"></a>

## CAN-FD SPAS indicators (trial)

`CanfdBlinkerControl`

Use comma SPAS indicators on Hyundai/Kia/Genesis CAN-FD vehicles with matching ECAN SPAS1/2 and valid driver input. Default OFF; reboot required. Disables the Jetson USB2CAN blinker path. The parking ECU is temporarily paused only during a requested signal and restored afterwards. Existing AutoBlinkerControl modes apply. Vehicle acceptance is required.

<!-- CARROT:AUTO:BEGIN CanfdBlinkerControl -->
<!-- CARROT:AUTO:SOURCE facts="d86d7274ce7d07bbe66b3fbd7377ba16c351bb416ec03e4887854fd2546a58ec" semantic="b9c8da21ba0961eca86e2eeeedd9232360297164deac532d95f215a0433ae12c" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **型別:** 開關
- **預設值:** `0`
- **範圍:** `0` ~ `1`
- **選單:** 車輛與硬體 \> 轉向燈控制 \> 輸出裝置
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END CanfdBlinkerControl -->

<!-- CARROT:MANUAL:BEGIN CanfdBlinkerControl -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END CanfdBlinkerControl -->

<!-- CARROT:SETTING:END CanfdBlinkerControl -->
