# 卡車避讓：實車資料收集與離線觀察

此分支把先前的影子分析工具帶到長期 Test 分支的 `3ad2e566c68d26a0b684f447529b124d7403040a` 基底，
並加入停車後的自動資料打包工具。它不會自行啟動辨識、顯示即時偵測結果或改變方向盤。
偏移數值只是離線候選；`applied_offset_m` 永遠為 0，`control_eligible` 為 false。
這還不是能在實車上自動避讓的版本，C4 安裝與執行也尚未實機驗證。

## 停車後自動打包

此功能只在卡車研究分支運行。C4 進入 offroad，並連續 15 秒確認裝置狀態有效、
已連接 Panda 且點火訊號關閉後，才開始處理最近一趟行程。等紅燈、P 檔但車輛仍通電
或裝置狀態不明，不會啟動打包。裝置溫度狀態為紅色或危險時也會暫停。
這些訊號不能獨立證明車輛的實際位置或靜止狀態。

程式把最近一趟行程中每個含有已關閉、非空前鏡頭影片與 rlog 的片段，分別保存為一個 ZIP：

```text
/data/media/0/truck-shadow-auto/<行程編號>--<片段編號>.zip
```

每個 ZIP 包含同一片段的 `rlog.zst`、`fcamera.hevc` 與記錄大小及 SHA-256 的 manifest。
程式不會自行上傳檔案。最後完成 ZIP 才會以正式檔名出現；打包時重新啟動或斷電，
未完成的檔案會在之後再次確認 offroad 時重試，前提是原始檔還在且裝置有電。
若 C4 很快斷電，這次停車不保證已完成，也不會延長裝置供電或阻止正常關機。
如果原始片段仍有 `.lock`、已損毀或遭清除，程式會保留待處理狀態而不自動移除原始鎖檔。

ZIP 總量上限 5 GiB；保留的可用空間也必須高於系統清理門檻並留餘裕。空間不足時
停止新增，**不會自動刪除已完成 ZIP 或原始紀錄**。如果另一趟行程開始，打包會中止；
下一次符合條件時接續。狀態資訊與已保存的檔案可在 C4 查詢：

```bash
cat /data/media/0/truck-shadow-auto/status.json
ls -lh /data/media/0/truck-shadow-auto/*.zip
```

`state: blocked` 的 `blocked` 欄位會列出原因；`missing_source` 且缺少 `fcamera.hevc`
表示該段沒有前鏡頭影片。`archive_quota` 或 `free_space_reserve` 表示暫停新增。
前鏡頭必須在那趟行程發生之前已開啟錄影：`RecordRoadCam` 為 1（一般鏡頭）或 2
（一般鏡頭加廣角）；目前設定值可以查看狀態檔中的 `record_road_cam_current`。
本工具不會自動變更錄影設定，關閉期間已經錯過的影片無法補錄。

上述自動流程已做電腦端模擬測試，但尚未在實際 C4 驗證；不要把看到的狀態當成
即時卡車辨識或避讓能力。

## 先準備一段實車紀錄

正常行車記錄需有同一段原始 `rlog.zst` 與 `fcamera.hevc`；請在安全停車、C4 轉為 offroad
後操作，不需為了收集資料刻意靠近大車。建議記下大車出現的大約時間、在左側或右側、
光線及遮蔽狀況，便於事後比對。影片、位置與車輛紀錄可能含個人資訊，交付前可自行確認。

若要手動指定其他片段，以下指令必須在含有此分支完整 openpilot 環境的 C4 上執行。
`list` 只列出同時有兩個原檔的紀錄；
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
