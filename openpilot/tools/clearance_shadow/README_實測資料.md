# 卡車避讓：實車資料收集與離線觀察

此分支把先前的影子分析工具帶到長期 Test 分支的 `3ad2e566c68d26a0b684f447529b124d7403040a` 基底，
並加入停車後的資料打包工具。它不會自行啟動辨識、顯示即時偵測結果或改變方向盤。
偏移數值只是離線候選；`applied_offset_m` 永遠為 0，`control_eligible` 為 false。
這還不是能在實車上自動避讓的版本，C4 安裝與執行也尚未實機驗證。

## 先準備一段實車紀錄

正常行車記錄需有同一段原始 `rlog.zst` 與 `fcamera.hevc`；請在安全停車、C4 轉為 offroad
後操作，不需為了收集資料刻意靠近大車。建議記下大車出現的大約時間、在左側或右側、
光線及遮蔽狀況，便於事後比對。影片、位置與車輛紀錄可能含個人資訊，交付前可自行確認。

以下指令必須在含有此分支完整 openpilot 環境的 C4 上執行。`list` 只列出同時有兩個原檔的紀錄；
`locked: true` 代表尚有 logger 鎖，不能打包。資料夾和內容未改名。

```bash
cd /data/openpilot
PYTHONPATH="$PWD/pydeps:$PWD${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m openpilot.tools.clearance_shadow.capture_segment list
```

複製清單中的 `segment` 值，取代下面範例，並將輸出名稱改成尚不存在的檔名：

```bash
TRUCK_SEGMENT='00000384--8d2511ca94--1'
PYTHONPATH="$PWD/pydeps:$PWD${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m openpilot.tools.clearance_shadow.capture_segment pack \
  --segment "$TRUCK_SEGMENT" --output /data/media/0/truck-shadow-01.zip
```

打包會確認 `IsOffroad`、拒絕尚有 `.lock` 的資料夾、檢查檔案沒有在複製途中改變，
並保留至少 1 GiB 剩餘空間；複製時會定期檢查 offroad 狀態，若讀到非 offroad 就中止並
刪除未完成的 ZIP。這不會阻止車輛啟動，實際狀態回報與時序仍待 C4 驗證。
它不改動原始紀錄。鎖定與檔案穩定性檢查不能單獨證明影片可完整解碼或與 log 每一格都對齊。
請使用新的輸出名稱；工具不覆寫既有 ZIP。

ZIP 內有兩份原檔及 `manifest.json`，其大小與 SHA-256 可在傳送到電腦後驗證，驗證不解壓：

```bash
python3 -m openpilot.tools.clearance_shadow.capture_segment verify /path/to/truck-shadow-01.zip
```

可用原本的檔案傳輸方式把 ZIP 傳到電腦，或上傳給協助分析的人；程式本身不會上傳。
需在完整 Carrot Python/cereal 環境執行 `export_rlog`，再用電腦端獨立 YOLO 環境回放，
詳細命令見 `docs/clearance_shadow_20261109.md`。本工具沒有把幾何 sidecar 放進 ZIP；
sidecar 應由 ZIP 中的同一段 rlog 產生，不能使用別段或重新剪輯的影片。

## 使用你的模型

`best.pt` 未包含在分支。使用者提供的模型原始 SHA-256：
`f8d996eec31105011940113a5880734cc7300cc0b43283ceedffc28a6398be82`。
請在電腦端以 SHA-256 核對後，將它作為既有離線回放命令的 `--weights`；不要把桌面版
YOLO/PyTorch 安裝進 C4 的駕駛環境。模型的 `rider`、`motor`、`bike` 分別對應
人、機車、自行車，以保留可能位於另一側的道路使用者；`train` 也作為障礙保留。
這只是名稱映射，不代表模型必定能偵測到這些對象。

已在電腦端用此 `best.pt` 與先前比較報告中的三張 336×190 原始縮圖，各重複輸入三次；
模型與 ByteTrack 介面可執行，三張圖都有維持相同的 truck 追蹤編號。紀錄見
`validation_best_pt_20261110.json`。重複同一張靜態圖片不代表連續影像追蹤或 C4 效能通過。

先前的 500 張 BDD pilot 中，210 個 truck 標註在信心門檻 0.65 的召回率是 18.1%；
即使下降門檻仍有漏判和誤判，且該資料不是台灣實車驗證。不要根據一次辨識成功、
候選偏移或本文件判斷此功能可控制車輛。

下一階段仍需左右側大車的原始連續影像與 rlog、台灣道路標註、追蹤與側向距離驗證，
以及 C4／Jetlink 的效能和隔離測試；這些尚未完成。
