<!-- CARROT:GENERATED schema="1" locale="zh-tw" group="VEH_CANFD" param="CanfdHDA2" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# CANFD HDA2 (0)

**選單:** 車輛與硬體 \> CANFD·HDA

---

<!-- CARROT:SETTING:BEGIN CanfdHDA2 -->
<a id="CanfdHDA2"></a>

## CANFD HDA2 (0)

`CanfdHDA2`

0: HDA1, 1: HDA2

<!-- CARROT:AUTO:BEGIN CanfdHDA2 -->
<!-- CARROT:AUTO:SOURCE facts="39f2ae39a8c8f9401cb35bd99e1fa583ba00e1c016808cbd65b61b1f0890cbb7" semantic="6b24754cbac58c945701508b8f8fc96985d82ba760a595087dd33c95e6210b76" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **型別:** 開關
- **預設值:** `0`
- **範圍:** `0` ~ `1`
- **選單:** 車輛與硬體 \> CANFD·HDA
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END CanfdHDA2 -->

<!-- CARROT:MANUAL:BEGIN CanfdHDA2 -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:SECTION:BEGIN BEHAVIOR -->
### 運作方式

- `0` — 將 Hyundai／Kia CAN FD 車輛視為 HDA1 配置。
- `1` — 使用 HDA2 CAN 匯流排配置。
<!-- CARROT:SECTION:END BEHAVIOR -->

<!-- CARROT:SECTION:BEGIN USAGE -->
### 使用方式

確認車輛的 HDA 及 CAN FD 配置，停妥後設定，並於下次行車檢查相關功能及故障訊息。
<!-- CARROT:SECTION:END USAGE -->

<!-- CARROT:SECTION:BEGIN REFERENCE -->
### 補充說明

<!-- CARROT:NOTICE level="WARNING" -->
> [!WARNING]
> 未經驗證的 CAN FD 配置，可能造成車輛警告或 CAN 故障。
<!-- CARROT:NOTICE:END -->
<!-- CARROT:SECTION:END REFERENCE -->
<!-- CARROT:MANUAL:END CanfdHDA2 -->

<!-- CARROT:SETTING:END CanfdHDA2 -->
