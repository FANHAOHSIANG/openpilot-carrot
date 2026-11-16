<!-- CARROT:GENERATED schema="1" locale="zh-tw" group="INDICATOR_OUTPUT" param="CanfdBlinkerKick" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# Panda/SPAS 轉向燈輸出

**選單:** 車輛與硬體 \> 轉向燈控制 \> 輸出裝置

---

<!-- CARROT:SETTING:BEGIN CanfdBlinkerKick -->
<a id="CanfdBlinkerKick"></a>

## Panda/SPAS 轉向燈輸出

`CanfdBlinkerKick`

透過Panda使用車輛SPAS報文傳送共用轉向燈請求。預設關閉。支援攝像頭SCC CAN-FD配置的IONIQ 5 PE、IONIQ 9和Grandeur GN7。 自動點亮使用自動轉向燈、手動變道轉向燈、手動轉彎轉向燈及模型觀察設定，與USB2CAN和BT2CAN共用啟動、保持和結束判斷。自動轉向燈0關閉自動請求，保留藍芽按鈕的單次請求。 開啟在下次OnRoad啟動生效，關閉立即生效，需要更新後的Panda韌體。開啟會停止USB2CAN和BT2CAN輸出，等待舊請求到期及獨佔輸出權，並在下次OnRoad關閉CanfdBlinkerControl。 真實撥杆優先並終止自動輸出。自動燈光反饋與轉向請求隔離。共用請求結束後停止SPAS輸出並恢復ECU預設會話，剩餘閃爍時間取決於車輛。 保留已有輸出和共用設定值。舊模型變道閃爍次數設定已移除，請使用共用設定。 手動變道和轉彎正常提前完成時，Panda/SPAS從首次傳送請求起至少保持2秒。實際撥杆操作、取消、輸入或車道錯誤會立即結束請求。實際閃爍次數取決於車輛。

<!-- CARROT:AUTO:BEGIN CanfdBlinkerKick -->
<!-- CARROT:AUTO:SOURCE facts="cbe7d58402788ffdb2b909af475412d4d6eaa02421cf14e63b382bd5dba32dc4" semantic="e3d01ebf21844e839abfc47d5fc08878416a9261d5535df9497959b72b96c157" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **型別:** 開關
- **預設值:** `0`
- **範圍:** `0` ~ `1`
- **選單:** 車輛與硬體 \> 轉向燈控制 \> 輸出裝置
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END CanfdBlinkerKick -->

<!-- CARROT:MANUAL:BEGIN CanfdBlinkerKick -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END CanfdBlinkerKick -->

<!-- CARROT:SETTING:END CanfdBlinkerKick -->
