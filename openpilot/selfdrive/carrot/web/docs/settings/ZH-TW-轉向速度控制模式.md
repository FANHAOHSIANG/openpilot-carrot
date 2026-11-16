<!-- CARROT:GENERATED schema="1" locale="zh-tw" group="SPEED_CURVE" param="TurnSpeedControlMode" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# 轉向速度控制模式

**選單:** 駕駛控制 \> 速度與減速 \> 彎道與轉彎

---

<!-- CARROT:SETTING:BEGIN TurnSpeedControlMode -->
<a id="TurnSpeedControlMode"></a>

## 轉向速度控制模式

`TurnSpeedControlMode`

0: 不使用, 1: 視覺, 2: 視覺 + 路線, 3: 路線 (始終)

<!-- CARROT:AUTO:BEGIN TurnSpeedControlMode -->
<!-- CARROT:AUTO:SOURCE facts="9f471a662745b3cd09c65968a331f72b858b09f30a92e1210f290dc0bb49a109" semantic="db2399ff8f834bd37741fa4c0751142f9ca87ceeeb55df6ad1bc86a9828f8ec6" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **型別:** 分段選擇
- **預設值:** `1`
- **範圍:** `0` ~ `3`
- **步長:** `1`
- **選單:** 駕駛控制 \> 速度與減速 \> 彎道與轉彎
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END TurnSpeedControlMode -->

<!-- CARROT:MANUAL:BEGIN TurnSpeedControlMode -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:SECTION:BEGIN BEHAVIOR -->
### 運作方式

選定值會依下列方式改變行為。

- `0` — 不使用
- `1` — 視覺
- `2` — 視覺＋導航路線
- `3` — 導航路線（持續使用）
<!-- CARROT:SECTION:END BEHAVIOR -->

<!-- CARROT:SECTION:BEGIN USAGE -->
### 使用方式

在相同彎道與路線導引條件下，每次調整一項，比較入彎前的目標及過彎速度。
<!-- CARROT:SECTION:END USAGE -->

<!-- CARROT:SECTION:BEGIN REFERENCE -->
### 補充說明

[相關英文操作指南](https://github.com/ajouatom/openpilot/blob/carrot-wip/docs/user/en/speed-deceleration.md)
<!-- CARROT:SECTION:END REFERENCE -->
<!-- CARROT:MANUAL:END TurnSpeedControlMode -->

<!-- CARROT:SETTING:END TurnSpeedControlMode -->
