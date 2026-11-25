<!-- CARROT:GENERATED schema="1" locale="zh" group="STEER_LANEMODE" param="ModelCurveCentering" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# 模型弯道居中修正

**菜单:** 驾驶控制 \> 转向 \> 车道模式

---

<!-- CARROT:SETTING:BEGIN ModelCurveCentering -->
<a id="ModelCurveCentering"></a>

## 模型弯道居中修正

`ModelCurveCentering`

仅适用于 CAN-FD IONIQ 5。使用模型转向时，若两侧车道线可靠且预测路径偏向弯道内侧，便朝车道中央微调转向目标。默认关闭。

<!-- CARROT:AUTO:BEGIN ModelCurveCentering -->
<!-- CARROT:AUTO:SOURCE facts="ade8e044168f48d9ce1251884053208e10f7a68177ca892d643fe3ad43cf17fc" semantic="93bb71bdc261b9cd8a21ddbe3c2243f790b32d7b9141d440191bda6e9e442b20" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **类型:** 开关
- **默认值:** `0`
- **范围:** `0` ~ `1`
- **菜单:** 驾驶控制 \> 转向 \> 车道模式
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END ModelCurveCentering -->

<!-- CARROT:MANUAL:BEGIN ModelCurveCentering -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END ModelCurveCentering -->

<!-- CARROT:SETTING:END ModelCurveCentering -->
