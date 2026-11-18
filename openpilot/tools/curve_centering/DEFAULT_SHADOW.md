# 獨立測試分支：預設影子觀察與紀錄

使用者要求的預設啟用只套用在 `test/carrot-pr52-integration-20261117`。
建立 Controls 時，未設定 `CURVE_CENTERING_SHADOW` 或值為 `1` 會啟動隔離觀察；
設成 `0`（或其他非 `1` 值）則不啟動。這不是 C4 時序資格認證，也不部署裝置。
既有 33.5 ms 故障測試尖峰、幾何與候選控制失敗證據都保留。

## 如何確認有紀錄

子程序每秒最多一筆 `curve_centering_shadow`，包含 `mode=process_shadow_only`、
`vehicle_output=false`、`now_ns`、資料年齡、排除理由、基準差、候選差與歷史差。
它經既有 logmessaged 寫入裝置 `/data/log/swaglog.*`，正常 logger 運作時也存為
rlog 的 `logMessage`。未新增 GPS、影片、裝置識別欄位或自動上傳；原有完整日誌
仍可能包含私人資訊。沒有紀錄不能直接當成通過，需確認日誌服務及初始化／停止錯誤。

把已有日誌複製到桌面後，僅抽出影子欄位：

```sh
python -m openpilot.tools.curve_centering.export_shadow /path/to/swaglog.* --output /tmp/curve-shadow.jsonl
python -m openpilot.tools.curve_centering.export_shadow --format rlog /path/to/rlog.zst --output /tmp/curve-shadow-rlog.jsonl
```

兩種輸入擇一即可。工具不連線、不上傳、不覆蓋已有輸出；排除外層 host／ctx 與非影子
事件。保留單調時鐘用於對齊，不將模型幾何當成獨立道路真值。資料不合格時會記錄理由，
不輸出候選。初始化／子程序例外可另外在原始日誌搜尋 `curve_centering_shadow_init_failed`
及 `curve_centering_shadow_worker_failed`，不需公開整份原始日誌。

## 關閉與故障退出

在**啟動 controlsd 的環境**設定 `CURVE_CENTERING_SHADOW=0`，下次正常建立控制程序時
不啟動觀察器。此值不是 Params／網頁按鈕，沒有熱切換；在另一個終端 export 不會改變
已運行程序。移除設定或設回 `1` 於下一次程序開始時恢復。不要為測試在行駛中重啟程序。

子程序失效、通道斷開、持續滿載（起始2秒寬限後連續200ms）會停止觀察，當次 controlsd
不自動重啟；暫時丟包則重設穩定期。既有實際控制計算、限制與致動輸出不採用影子結果。

## 桌面可重現驗證

具備原生依賴的桌面使用全新暫存路徑；此程式拒絕非 PC 平台：

```sh
OPENPILOT_PREFIX=pr52synthetic-defaultcheck PARAMS_ROOT=/tmp/pr52-defaultcheck-params \
  PYTHONPATH="$PWD" python -m openpilot.tools.curve_centering.process_bench \
  --output /tmp/pr52-defaultcheck --seconds 40 --mode default --backend process \
  --load-location worker --stall-seconds 1 --record-logs
```

`--mode default` 移除環境覆寫，實測程式的預設值。`--mode off` 驗證明確關閉。
`--record-logs` 啟動真正 logmessaged，只把日誌目錄改到該測試的 `swaglog/`；
控制程式、子程序及日誌傳輸保持原生。沒有啟動車輛/CAN消費者，也沒有真實行車輸入。
此次測試結果見 DEFAULT_SHADOW_VALIDATION.json；先前結果見 PROCESS_ISOLATION.md。


驗證結果：206項回歸與13項原生啟動測試通過。預設開啟40秒、真正logmessaged落盤
取得24筆觀察（11筆非零比較）及2筆退出紀錄；明確關閉12秒沒有工作程序、擷取或影子紀錄。
新測試最長發布間隔29.439ms，不取代原33.519ms負面結果。
Swaglog及合成zstd rlog匯出26筆完全一致；這不是私人真實行車回放。


## 相機低幀率回報後的修正

已修正影子程序繼承控制程序即時排程／核心綁定的缺陷，詳見
[SCHEDULER_FIX.md](SCHEDULER_FIX.md)。目前啟動前指定一般排程，啟動後立即降低到
nice19，C4使用背景核心0–3；套用失敗就退出觀察，不退回即時排程。
紀錄新增 `worker_scheduler`、`worker_nice`、`worker_affinity` 供核對。
照片的確切故障原因與C4恢復情況仍未獲證；不取消或放寬相機警告。
