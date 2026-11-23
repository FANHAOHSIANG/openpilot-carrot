<!-- CARROT:GENERATED schema="1" locale="zh-tw" group="INDICATOR_OUTPUT" param="CanfdBlinkerKickMode" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# Panda/SPAS 傳送方式

**選單:** 車輛與硬體 \> 轉向燈控制 \> 輸出裝置

---

<!-- CARROT:SETTING:BEGIN CanfdBlinkerKickMode -->
<a id="CanfdBlinkerKickMode"></a>

## Panda/SPAS 傳送方式

`CanfdBlinkerKickMode`

「Panda/SPAS 轉向燈輸出」傳送轉向燈指令的方式。預設1。 0: 僅在泊車ECU應答暫停請求且原廠SPAS幀停止後傳送; 無應答則不點亮(IONIQ 5 PE 未應答)。 1: 搭載。ECU無應答時, panda把我們的SPAS幀緊跟在原廠SPAS幀之後傳送, 同一ID不會同時起始, 避免衝突。ECU應答時與0相同。 - 適用車型與接線與「Panda/SPAS 轉向燈輸出」相同。

<!-- CARROT:AUTO:BEGIN CanfdBlinkerKickMode -->
<!-- CARROT:AUTO:SOURCE facts="ba9ae11d91047c9b95882d49e294fdcfe7730b5cada0a226adbcf6db9278afac" semantic="70568faca97452808ebd34cfcdcab63fc7b42577cc2420a1aeaf4adf8e066b41" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **型別:** 開關
- **預設值:** `1`
- **範圍:** `0` ~ `1`
- **選單:** 車輛與硬體 \> 轉向燈控制 \> 輸出裝置
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END CanfdBlinkerKickMode -->

<!-- CARROT:MANUAL:BEGIN CanfdBlinkerKickMode -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END CanfdBlinkerKickMode -->

<!-- CARROT:SETTING:END CanfdBlinkerKickMode -->
