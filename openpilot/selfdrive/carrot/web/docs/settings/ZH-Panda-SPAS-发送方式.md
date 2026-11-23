<!-- CARROT:GENERATED schema="1" locale="zh" group="INDICATOR_OUTPUT" param="CanfdBlinkerKickMode" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# Panda/SPAS 发送方式

**菜单:** 车辆与硬件 \> 转向灯控制 \> 输出设备

---

<!-- CARROT:SETTING:BEGIN CanfdBlinkerKickMode -->
<a id="CanfdBlinkerKickMode"></a>

## Panda/SPAS 发送方式

`CanfdBlinkerKickMode`

「Panda/SPAS 转向灯输出」发送转向灯指令的方式。默认1。 0: 仅在泊车ECU应答暂停请求且原厂SPAS帧停止后发送; 无应答则不点亮(IONIQ 5 PE 未应答)。 1: 搭载。ECU无应答时, panda把我们的SPAS帧紧跟在原厂SPAS帧之后发送, 同一ID不会同时起始, 避免冲突。ECU应答时与0相同。 - 适用车型与接线与「Panda/SPAS 转向灯输出」相同。 模式1确认ECU无应答后，只要原厂SPAS接收与输出所有权持续正常，可从确认时刻起60秒内复用该结果，避免下一请求再次等待0.4秒。接收中断、新ECU应答、所有权丢失、设置变化或到期后重新确认。模式0仍须ECU应答，原厂帧同步与驾驶员取消条件不变。

<!-- CARROT:AUTO:BEGIN CanfdBlinkerKickMode -->
<!-- CARROT:AUTO:SOURCE facts="c2ab9d217d8b36b546dade7893adff61fa296aa5d06046f579ccd22545f35a81" semantic="70568faca97452808ebd34cfcdcab63fc7b42577cc2420a1aeaf4adf8e066b41" review="needs_review" -->
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
