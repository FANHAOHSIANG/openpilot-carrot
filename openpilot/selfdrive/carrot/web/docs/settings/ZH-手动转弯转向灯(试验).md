<!-- CARROT:GENERATED schema="1" locale="zh" group="INDICATOR_AUTO" param="ManualTurnIndicator" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# 手动转弯转向灯（试验）

**菜单:** 车辆与硬件 \> 转向灯控制 \> 自动点亮

---

<!-- CARROT:SETTING:BEGIN ManualTurnIndicator -->
<a id="ManualTurnIndicator"></a>

## 手动转弯转向灯（试验）

`ManualTurnIndicator`

结合驾驶员转向力、方向盘转动及车辆实际旋转识别左右转弯，独立于ATC，支持车道线不清晰的路口。起始速度5–60km/h，同向转向力持续0.15秒，转角至少42度且增加22度，并确认同向车身旋转。方向盘回到±15度且旋转稳定、驾驶员反向转向或持续30秒后结束。默认关闭，适用于Ioniq 5 PE、支持的转向灯设备及自动转向灯模式1或2。停车场转弯也可能触发，弯道及避让动作可能误触发，实车灯光验证待完成。 手动变道指示期间满足同向手动转弯条件时，延续原请求并按转弯完成条件跟踪。 路口边界位置跳变不会重置通过驾驶员转向力、转角增加和实际旋转确认的手动转弯。D挡确认静止时，零附近的微小负速度估计不会终止已建立的指示。 支持的Panda/SPAS输出使用相同设置和判断，适用于摄像头SCC CAN-FD配置的IONIQ 5 PE、IONIQ 9和Grandeur GN7。 手动变道和转弯正常提前完成时，Panda/SPAS从首次发送请求起至少保持2秒。实际拨杆操作、取消、输入或车道错误会立即结束请求。实际闪烁次数取决于车辆。

<!-- CARROT:AUTO:BEGIN ManualTurnIndicator -->
<!-- CARROT:AUTO:SOURCE facts="f4864f0b403693c668ec65b815a8919a14a52dda1354e208f84f53d8b3755d9b" semantic="e4bbf6a833570ad6bb05e5eb7b686cd71385572d1c15c465dd90e155a3b801b4" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **类型:** 开关
- **默认值:** `0`
- **范围:** `0` ~ `1`
- **菜单:** 车辆与硬件 \> 转向灯控制 \> 自动点亮
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END ManualTurnIndicator -->

<!-- CARROT:MANUAL:BEGIN ManualTurnIndicator -->
<!-- CARROT:REVIEW reviewed-for="e08aa7e7e006ddb909a0060571a3f7983d6c70f1249f7f29cc42c19e87f3451a" reviewed-at="2026-11-14T02:05:14Z" -->
<!-- CARROT:SECTION:BEGIN BEHAVIOR -->
### 动作

结合驾驶员同向转向力、方向盘角度增加及新鲜的车身旋转数据识别转弯。独立于ATC和横向控制激活状态，灯光反馈受到自动转向请求隔离。

方向盘回正且旋转稳定后结束，驾驶员反向转向、输入异常或关闭设置时取消。
上次指示保持结束满2秒且两侧转向灯连续熄灭1秒后，才重新识别新的手动转弯。这两个等待时间同时计算。
手动变道指示期间满足同向手动转弯条件时，延续原请求及确认，并改按转弯完成条件跟踪，不重新轻触。
<!-- CARROT:SECTION:END BEHAVIOR -->

<!-- CARROT:SECTION:BEGIN USAGE -->
### 使用

Git Pull后重启comma并开启此选项。适用于Ioniq 5 PE、支持的转向灯设备及自动转向灯模式1或2。
<!-- CARROT:SECTION:END USAGE -->

<!-- CARROT:SECTION:BEGIN REFERENCE -->
### 参考

停车场通道、坡道及泊车转向也可能触发。无清晰车道线的弯道和避让动作可能误触发，实际灯光验证待完成。
<!-- CARROT:SECTION:END REFERENCE -->

<!-- CARROT:MANUAL:END ManualTurnIndicator -->

<!-- CARROT:SETTING:END ManualTurnIndicator -->
