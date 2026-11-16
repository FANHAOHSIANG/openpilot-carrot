<!-- CARROT:GENERATED schema="1" locale="zh" group="INDICATOR_OUTPUT" param="CanfdBlinkerKickMode" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# Panda/SPAS 发送方式

**菜单:** 车辆与硬件 \> 转向灯控制 \> 输出设备

---

<!-- CARROT:SETTING:BEGIN CanfdBlinkerKickMode -->
<a id="CanfdBlinkerKickMode"></a>

## Panda/SPAS 发送方式

`CanfdBlinkerKickMode`

「Panda/SPAS 转向灯输出」发送转向灯指令的方式。默认1。 0: 仅在泊车ECU应答暂停请求且原厂SPAS帧停止后发送; 无应答则不点亮(IONIQ 5 PE 未应答)。 1: 搭载。ECU无应答时, panda把我们的SPAS帧紧跟在原厂SPAS帧之后发送, 同一ID不会同时起始, 避免冲突。ECU应答时与0相同。 - 适用车型与接线与「Panda/SPAS 转向灯输出」相同。

<!-- CARROT:AUTO:BEGIN CanfdBlinkerKickMode -->
<!-- CARROT:AUTO:SOURCE facts="259e783979e755d472e7faa71bbcee96990ccb13ed858c6ea853b8e12bb89f52" semantic="50e1f21152cd48de144012c02d1efe05b4cc7b29ef1a56a4eaec16e1fb980935" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **类型:** 开关
- **默认值:** `1`
- **范围:** `0` ~ `1`
- **菜单:** 车辆与硬件 \> 转向灯控制 \> 输出设备
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END CanfdBlinkerKickMode -->

<!-- CARROT:MANUAL:BEGIN CanfdBlinkerKickMode -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END CanfdBlinkerKickMode -->

<!-- CARROT:SETTING:END CanfdBlinkerKickMode -->
