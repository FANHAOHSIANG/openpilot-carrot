<!-- CARROT:GENERATED schema="1" locale="zh" group="INDICATOR_AUTO" param="AutoBlinkerControl" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# 自动转向灯

**菜单:** 车辆与硬件 \> 转向灯控制 \> 自动点亮

---

<!-- CARROT:SETTING:BEGIN AutoBlinkerControl -->
<a id="AutoBlinkerControl"></a>

## 自动转向灯

`AutoBlinkerControl`

0：关闭（保留蓝牙轻触）。1：低于5km/h蓝牙保持至转弯结束，从ATC audioTurn提示开始保持，路口停车时不熄灭，实际转弯后方向盘回正时解除。2：另含实际开始的ATC变道，等待时不亮。同方向取消保持，反方向切换。原车拨杆优先。需要支持的Jetson USB-CAN/B1车辆。 ATC在确认发送完成但未亮灯时最多重试一次。有效TBT坐标与车辆GPS确认直行通过后自动取消；位置不可靠时不使用该位置取消判断。 TBT按audioTurn距离及行驶距离跟踪至转弯点后30米。确认对应方向转角超过30度且车身方向变化至少20度后，车速至少1km/h时方向盘回到±15度以内立即结束保持。进入转弯前的信号灯停车仍保持。新的下一转弯提示在当前转弯结束后接续；对应方向转角达到30度后，驾驶员反向施力使转角越过零点进入反方向时取消。已确认发送及亮灯的TBT保持不因接收端driver\_override状态单独解除。不能保证原车灯立即熄灭。 按巡航 CANCEL 会停止自动转向灯请求并解除自动保持。泊车转动方向盘不会重新触发；用 SET/RES 或 +/− 解除巡航取消状态后，新动作才可触发。原车拨杆和蓝牙转向灯按钮仍可手动使用。 支持的Panda/SPAS输出使用相同设置和判断，适用于摄像头SCC CAN-FD配置的IONIQ 5 PE、IONIQ 9和Grandeur GN7。 USB2CAN/BT2CAN已确认的TBT保持沿用接收器driver\_override处理。Panda/SPAS确认真实拨杆操作后结束TBT保持。

<!-- CARROT:AUTO:BEGIN AutoBlinkerControl -->
<!-- CARROT:AUTO:SOURCE facts="692a879f13621e80deb4648cfe0e2ce791ea65f6344923ec2f0d4af78f9f84eb" semantic="f201e7abb802048e9cfb08de91f28ef854b93e6bf418d3ce82001bb17b91dafc" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **类型:** 分段选择
- **默认值:** `0`
- **范围:** `0` ~ `2`
- **步长:** `1`
- **菜单:** 车辆与硬件 \> 转向灯控制 \> 自动点亮
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END AutoBlinkerControl -->

<!-- CARROT:MANUAL:BEGIN AutoBlinkerControl -->
<!-- CARROT:REVIEW reviewed-for="edd05659292aebc71be712906d3faaadf71c30551e5a372287abb2bf65bd60ca" reviewed-at="2026-11-10T10:39:14.890627+00:00" -->
<!-- CARROT:SECTION:BEGIN BEHAVIOR -->
### 行为

在支持的车辆上管理BT和ATC实际转向灯请求及保持。

确认进入转弯后，行驶中方向盘回到±15度以内即正常结束，也使用转弯点后的行驶距离判断结束。对应方向转角达到30度后，驾驶员反向施力使转角越过零点进入反方向时取消。

已确认发送及亮灯的TBT保持可在接收端driver_override状态下继续至转弯结束。缺少首次发送确认时无法启用保持。新的下一转弯提示在当前转弯结束后接续。

按巡航 CANCEL 会停止自动转向灯请求并解除自动保持。泊车转动方向盘不会重新触发；用 SET/RES 或 +/− 解除巡航取消状态后，新动作才可触发。原车拨杆和蓝牙转向灯按钮仍可手动使用。
<!-- CARROT:SECTION:END BEHAVIOR -->
<!-- CARROT:MANUAL:END AutoBlinkerControl -->

<!-- CARROT:SETTING:END AutoBlinkerControl -->
