<!-- CARROT:GENERATED schema="1" locale="zh" group="STEER_LANECHANGE" param="AutoTurnControlRightLaneChange" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# 右转前自动变道距离(米)

**菜单:** 驾驶控制 \> 转向 \> 变道 (自动转向)

---

<!-- CARROT:SETTING:BEGIN AutoTurnControlRightLaneChange -->
<a id="AutoTurnControlRightLaneChange"></a>

## 右转前自动变道距离(米)

`AutoTurnControlRightLaneChange`

0米关闭，最大可设置2000米。最新导航明确确认为高速公路或汽车专用道路时使用设定距离；普通道路、道路类型未知或信息过期时使用设定值与500米中的较小值。设为2000米时，普通道路500米、高速公路2000米。不会仅凭车道数量判断高速公路。保留原有设置值。原开启设置在启动时转换为250米。附加于ATC模式1或2。车速至少10km/h时，距TBT右转或右侧分岔设定距离以内且尚未开始转弯时请求右转向灯。需要protocol-matched USB2CAN, BLE or Panda/SPAS、AutoBlinkerControl=2及LaneChangeNeedTorque=0。后方仅检查有效原车BSD警告，不使用角雷达距离。右侧目标车道的前方车辆当前距离及按相对速度预测3秒后的距离均须至少5米。前雷达故障或数据过期时不启动。请求前转向会重新确认条件，请求后驾驶员干预会取消。 低于30km/h开始的信号始终仅作显示；至少30km/h开始时才进入既有变道流程。右侧车道线到道路边缘须至少2.5米。 原生Kick也将至少30km/h启动且通过条件检查的ATC请求的实际灯光反馈交给既有变道判断。仅显示的信号和取消后的剩余闪烁仍不触发自动转向。保留4秒开始等待和原有取消条件，不保证最少闪烁次数。

<!-- CARROT:AUTO:BEGIN AutoTurnControlRightLaneChange -->
<!-- CARROT:AUTO:SOURCE facts="d177a23445eaed246406a432ca63b4fa86ece42cbf1f9630f35949812f8a8e4a" semantic="c7837f43c48a0b5200b4346241f2335323cffcce3eff5cbf9e02db29380b7032" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **类型:** 数值
- **默认值:** `0`
- **范围:** `0` ~ `2000`
- **步长:** `50`
- **菜单:** 驾驶控制 \> 转向 \> 变道 (自动转向)
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END AutoTurnControlRightLaneChange -->

<!-- CARROT:MANUAL:BEGIN AutoTurnControlRightLaneChange -->
<!-- CARROT:REVIEW reviewed-for="3008498ad9b26c4e6721da72acaa56057939a66d7d15c51954adbc9bb64b1584" reviewed-at="2026-11-02T22:15:29.552199+00:00" -->
<!-- CARROT:SECTION:BEGIN BEHAVIOR -->
### 行为

0米关闭附加功能，增大数值会在右转或右侧分岔前更远处检查条件。250米对应原有范围，原开启设置在重启时转换为250米。

车速至少10km/h时检查右侧车道、道路边缘、有效BSD及当前和3秒预测前车距离。低于30km/h开始的信号仅作显示，达到30km/h时开始的信号进入既有变道判断。
<!-- CARROT:SECTION:END BEHAVIOR -->
<!-- CARROT:MANUAL:END AutoTurnControlRightLaneChange -->

<!-- CARROT:SETTING:END AutoTurnControlRightLaneChange -->
