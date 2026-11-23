<!-- CARROT:GENERATED schema="1" locale="zh" group="INDICATOR_AUTO" param="ManualLaneChangeIndicator" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# 手动变道转向灯（试验）

**菜单:** 车辆与硬件 \> 转向灯控制 \> 自动点亮

---

<!-- CARROT:SETTING:BEGIN ManualLaneChangeIndicator -->
<a id="ManualLaneChangeIndicator"></a>

## 手动变道转向灯（试验）

`ManualLaneChangeIndicator`

手动变道转向灯不再以左侧线色或中央线分类、右侧道路边缘间距限制点灯。仍要求车速至少5km/h、驾驶员意图、实际边界接近、有效车道宽度、连续性和近期目标线可信度，不请求自动转向。两秒内结束的接近请求后，独立确认的同向手动转弯可发出新请求；新的反向边界接近在双灯连续熄灭一秒后可重新确认。拨杆、反向灯、无效输入和取消仍优先，保留转向反馈隔离。接近中央线或驶向路外也可能点灯。

<!-- CARROT:AUTO:BEGIN ManualLaneChangeIndicator -->
<!-- CARROT:AUTO:SOURCE facts="acf216d160f59b1b4df56c91edcadfed22a15ccfa657e71bc8ab157f04e576bf" semantic="b054132b7f6fb71e55d9758b1d6cdc54cb75fac679420524d7691e6c8c56817a" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **类型:** 开关
- **默认值:** `0`
- **范围:** `0` ~ `1`
- **菜单:** 车辆与硬件 \> 转向灯控制 \> 自动点亮
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END ManualLaneChangeIndicator -->

<!-- CARROT:MANUAL:BEGIN ManualLaneChangeIndicator -->
<!-- CARROT:REVIEW reviewed-for="d96432b8f8ff840459f65cab076ba12f6d57b1d333e585a4be25652182e1e7ba" reviewed-at="2026-11-14T02:05:14Z" -->
<!-- CARROT:SECTION:BEGIN BEHAVIOR -->
### 行为

结合近期驾驶员转向意图与连续边界接近进行显示。开始时确认目标线置信度至少10%，并应用左侧中央线和右侧道路边缘排除条件。

请求后跟踪完成、返回及输入失效，不请求自动转向。保持请求结束后原车轻触闪灯仍可能继续。
根据测得的车道边界接近速度预测0.3秒后的位置，提前请求转向灯。车体中心至边界的距离阈值从0.9米最多提前至1.2米，仍要求至少0.15米实际接近、驾驶员意图及两侧边界一致移动。

手动及模型显示仅在请求时间、方向和拨杆计数一致时有限识别自身轻触反馈。反向输入、拨杆锁定或接收端检测到驾驶员介入时取消。先于发送完成应答的点灯反馈会短暂记忆，但保持仍须匹配应答；短暂发送期间同方向人工操作无法仅凭这些信息完全区分。
车速达到5公里/小时且检测到驾驶员转向并实际靠近相邻车道线时，可请求对应方向的转向灯。
边界回退持续0.15秒才取消接近跟踪，回退期间暂停新点灯。近期有驾驶员意图，且两侧边界同向移动、车道宽度一致时，允许有限的位置变化并继续跟踪。

B1 第5版允许已确认的自身轻触回讯持续穿过闪灯的熄灭间隔。轻触结束后收到中立回讯即关闭此允许，后续拨杆回讯会取消所有权；反侧灯、原始驾驶员输入、CAN异常及租约到期仍会取消。软件回放不代表实际保持或取消性能验收。
<!-- CARROT:SECTION:END BEHAVIOR -->
<!-- CARROT:MANUAL:END ManualLaneChangeIndicator -->

<!-- CARROT:SETTING:END ManualLaneChangeIndicator -->
