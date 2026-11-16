<!-- CARROT:GENERATED schema="1" locale="zh" group="VEH_CANFD" param="CcncTrafficBackground" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# CCNC 仪表信号灯背景

**菜单:** 车辆与硬件 \> CANFD·HDA

---

<!-- CARROT:SETTING:BEGIN CcncTrafficBackground -->
<a id="CcncTrafficBackground"></a>

## CCNC 仪表信号灯背景

`CcncTrafficBackground`

0: 关闭(默认, 背景与以前相同), 1: 开启。0 只关闭此项目(始终生效的仪表修正见「CCNC 仪表原厂式显示」)。 openpilot 检测到信号灯时改变 CCNC 仪表背景: 检测到红灯期间为红色背景, 变绿后仅2秒为绿色背景。与设备画面信号灯显示使用相同判断(longitudinalPlan.trafficState)。信号灯背景优先于巡航和转弯背景。 - 适用: 与「CCNC 仪表原厂式显示」相同的车型(现代·起亚·捷尼赛思 CAN-FD 车型, 摄像头 SCC 且使用 openpilot 纵向控制(HyundaiCameraSCC 1·2), 并已收到摄像头的 CCNC 仪表报文 0x161), 约1秒内生效。 - 背景值 5(红)、8(绿)不在 DBC 中, 已在 IONIQ 5 PE 仪表上确认。

<!-- CARROT:AUTO:BEGIN CcncTrafficBackground -->
<!-- CARROT:AUTO:SOURCE facts="168138aaf1eee20041e9eb9b7b17bee6b2d1792647d449afdd15ef25dc80995c" semantic="a384d27d552cb1006f160c4f53c1c2198356bc1f61e0b307e0a7710e03354404" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **类型:** 开关
- **默认值:** `0`
- **范围:** `0` ~ `1`
- **菜单:** 车辆与硬件 \> CANFD·HDA
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END CcncTrafficBackground -->

<!-- CARROT:MANUAL:BEGIN CcncTrafficBackground -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END CcncTrafficBackground -->

<!-- CARROT:SETTING:END CcncTrafficBackground -->
