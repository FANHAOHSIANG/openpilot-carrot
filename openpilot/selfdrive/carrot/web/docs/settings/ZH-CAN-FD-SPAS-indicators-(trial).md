<!-- CARROT:GENERATED schema="1" locale="zh" group="INDICATOR_OUTPUT" param="CanfdBlinkerControl" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# CAN-FD SPAS indicators (trial)

**菜单:** 车辆与硬件 \> 转向灯控制 \> 输出设备

---

<!-- CARROT:SETTING:BEGIN CanfdBlinkerControl -->
<a id="CanfdBlinkerControl"></a>

## CAN-FD SPAS indicators (trial)

`CanfdBlinkerControl`

Use comma SPAS indicators on Hyundai/Kia/Genesis CAN-FD vehicles with matching ECAN SPAS1/2 and valid driver input. Default OFF; reboot required. Disables the Jetson USB2CAN blinker path. The parking ECU is temporarily paused only during a requested signal and restored afterwards. Existing AutoBlinkerControl modes apply. Vehicle acceptance is required.

<!-- CARROT:AUTO:BEGIN CanfdBlinkerControl -->
<!-- CARROT:AUTO:SOURCE facts="d22e070c2045b409e879c4678f7fde134d713d6372a5595bed83d8ce29d6ff81" semantic="b9c8da21ba0961eca86e2eeeedd9232360297164deac532d95f215a0433ae12c" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **类型:** 开关
- **默认值:** `0`
- **范围:** `0` ~ `1`
- **菜单:** 车辆与硬件 \> 转向灯控制 \> 输出设备
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END CanfdBlinkerControl -->

<!-- CARROT:MANUAL:BEGIN CanfdBlinkerControl -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END CanfdBlinkerControl -->

<!-- CARROT:SETTING:END CanfdBlinkerControl -->
