# 高德車機版／一般版與 C4 視覺離線觀察

兩個 Test 分支的 cereal/services.py 已將 modelV2、road edges、GPS、livePose、accelerometer、gyroscope、carState、clocks、carrotNavi 納入既有完整 rlog。此變更新增離線匯出，不新增常駐程序、不修改 manager/loggerd/cereal schema/planner/車控、不需要 Mac 或額外模型。一般 C4 上傳完整 rlog 後即可離線處理，不需要行駛中執行終端機。

```bash
# 在 repository 的 openpilot 執行環境中（tools.lib.logreader 可 import）
python3 tools/carrot_navi_lab/gaode_vision_export.py --rlog /path/to/segment2/rlog.zst /path/to/segment3/rlog.zst --out /tmp/gaode-vision.jsonl
```

若 repository root 外層含 openpilot 目錄，先依該環境設定 PYTHONPATH（內層 openpilot 與外層 repository root），或從內層執行 ../tools/carrot_navi_lab/gaode_vision_export.py。輸出新 JSONL 不覆蓋舊檔。每片段獨立處理；缺失、無效及時間回退保留統計。

- 每 10/20/30/40/60m：四條車道線及其機率、兩道路邊界及標準差、可見連續車道數候選、自車車道寬與中心、模型路徑、曲率候選及視覺失效原因。僅近端可見的 1–3 條候選，不能推斷整條道路總車道數、自車絕對車道序號或分合流拓撲。道路邊界 std 不是機率。
- GPS、IMU、livePose、車速與導航接收狀態另有時間戳；GPS WGS84 與導航未知 CRS 分開保留；clocks 只能生成 C4 wall-clock 候選，Android 與 C4 的時鐘偏差仍需獨立驗證。每片段不跨缺口延伸，無時間錨則 null。
- 僅依照既有 C4 導航封包中 meta.present 保留有效候選，保留接收/來源時戳及序號；非地圖正確性驗證。Carrot Bridge wide.87 ZIP 可同時匯出；尚無自動跨裝置對時、HUD 新圖示、車道匹配或控制整合。
- 所有輸出 control_usable=false。紀錄含位置，不公開。回歸測試為合成資料；未實機執行及未下載使用者 rlog。
