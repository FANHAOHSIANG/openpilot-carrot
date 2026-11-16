<!-- CARROT:GENERATED schema="1" locale="zh" group="VEH_CANFD" param="CcncClusterDisplay" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# CCNC 仪表原厂式显示

**菜单:** 车辆与硬件 \> CANFD·HDA

---

<!-- CARROT:SETTING:BEGIN CcncClusterDisplay -->
<a id="CcncClusterDisplay"></a>

## CCNC 仪表原厂式显示

`CcncClusterDisplay`

0: 关闭(默认), 1: 开启。0 只关闭下列项目; HDP 车距显示·弹窗、侧方方框→灰色车辆、停车时转向图标的修正与此设置无关, 始终生效。 适用: 现代·起亚·捷尼赛思 CAN-FD 车型, 摄像头 SCC 且使用 openpilot 纵向控制(HyundaiCameraSCC 1·2), 并已收到摄像头的 CCNC 仪表报文 0x161(HDP 图标需 0x162)。openpilot 修改并重新发送这些报文, 像原厂 HDA2 一样在仪表上显示 openpilot 状态。约1秒内生效。 - 车道线: 模型车道线概率持续1秒以上低于0.08且摄像头也看不到时不显示该线(达到0.12再显示, 橙色线保留)。IONIQ 9、EV9 保持原有车道线显示。 - 虚线: 摄像头识别为虚线的车道线显示为虚线(IONIQ 5 PE、Grandeur GN7、EV4)。 - 车道高亮: 转向工作时按状态改变车道颜色。无车道模式绿色、车道模式天蓝色、转向角误差持续0.3秒黄色、转向极限红色、变道中绿色。有隐藏车道线时不改变。 - 前车圆环: 前车可见时, 巡航中蓝色圆环位于 openpilot 保持的目标车距, 非巡航时显示白色圆环。 - 弹窗: 巡航开启或解除时显示原厂提示弹窗2秒。 - 警告文字: 部分 openpilot 警告(车速过高、转向/SCC 不可用、转向极限、CAN/传感器异常)显示为原厂文字。转向极限(注意周围)文字同时像原厂一样发出1秒双响提示音。DBC 未列出的文字仅在 IONIQ 5 PE、Grandeur GN7、EV4 上显示。 - HDP 图标: 巡航或转向工作时点亮 HDP 图标(IONIQ 5 PE、Grandeur GN7、EV4)。

<!-- CARROT:AUTO:BEGIN CcncClusterDisplay -->
<!-- CARROT:AUTO:SOURCE facts="9aa20264a3d8343173252951a694838809ec73c6a3a888033be201954578e0e0" semantic="51f05ac1b11c155f7bc0190c1fc950a3b08c18761a77b6a68f9ed9e16b394137" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **类型:** 开关
- **默认值:** `0`
- **范围:** `0` ~ `1`
- **菜单:** 车辆与硬件 \> CANFD·HDA
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END CcncClusterDisplay -->

<!-- CARROT:MANUAL:BEGIN CcncClusterDisplay -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END CcncClusterDisplay -->

<!-- CARROT:SETTING:END CcncClusterDisplay -->
