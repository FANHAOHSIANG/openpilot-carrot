# Carrot 過彎置中研究台 v0.1

目標是找出左右彎偏離中央的來源，讓後續路徑或轉向修正有可重現的依據。
本版提供即時只讀監看、離線 rlog 分析、繁體中文回放頁與結構化 JSON。
**沒有自動調參、控制輸出或新訓練的駕駛模型，也沒有修改既有規劃器。**

## 看什麼

同一模型時間下比較：

1. `modelV2.position`：原始模型預測路徑。
2. `lateralPlan.dPathPoints`：規劃器送入 MPC 的路徑；依本分支實作配對該模型 `position.x`。
3. `lateralPlan.position`：MPC 預測位置。
4. `modelV2.laneLines[1:3]`：左右內側車道線及其幾何中心。

以 `lateralPlan.modelMonoTime` **完全匹配** `modelV2.logMonoTime`；不使用最近一筆替代。
車況、控制器狀態取模型時間之前的最新有效訊息；預設容許 200 ms，規劃延遲最多 300 ms。
輸入不同 x 格點分別插值，不外推。左右偏差以道路中心切線的法向近似換算。
MPC 輸入路徑偏差是前方 10/20/30 m 中有效點的偏差中位數；P95 是這個數值絕對值的畫面分布。
這些預測點不是車輛將來實際走過的軌跡。

**控制來源限制：** 本分支的 Hyundai 模型模式直接使用 `modelV2.action.desiredCurvature`，
經平滑與曲率限制後送出；此時 `dPathPoints` 與 MPC 預測仍會產生，但不是控制來源。
`useLaneLines=true` 也還需核對 `UseLaneLineCurveSpeed` 等控制器條件。
本工具的 `request_*` JSON 欄位保留舊名稱以相容資料格式，僅表示 MPC 輸入。
不能把它的偏差或 `PathOffset` 直接當成實際車輛偏移原因。
另列出模型目標曲率、模型時間之前的最新送出曲率與回授估計曲率，供控制來源核對；
三者不能視為同一模型影格的即時因果反應，回授估計也不是獨立道路真值。

`origin_offset_m` 是模型座標原點相對辨識車道中心的估計，**不是經獨立感測確認的車身中心**。
只有提供量測過的 `--vehicle-center-y` 才顯示車身中心估計；再提供 `--vehicle-width` 才計算側邊餘量。
右側為正，左側為負。沒有路緣/護欄實測距離，也不把方向盤角度誤差當車道位置誤差。

## 回放已下載的 Log

在此儲存庫根目錄執行（Python 3.12、pycapnp、zstandard）：

```bash
python3 -m openpilot.tools.curve_centering.replay /path/to/rlog.zst --output /path/to/centering-report
```

可列出多個本機檔案，或用 shell glob。輸出 `centering.html`、`centering.json`。
HTML 可直接在瀏覽器開啟，無外部字型、CDN、AI API 或遙測上傳。
JSON 保留每畫面證據、輸入雜湊、服務數量、排除原因與偏移候選，供進一步 AI/人工審查。
重複檔案依 SHA-256 略過；解析失敗或尾端不完整的檔案整檔排除並回傳 exit code 2。
其他完整檔案仍產生報告。每個檔案重設時間狀態，不假裝缺少前段的資料是連續行程。

## 即時只讀監看

在有完整 openpilot 執行環境的 C4 上，停車時手動啟動；原本的駕駛程式保持運作：

```bash
cd /data/openpilot
python3 -m openpilot.tools.curve_centering.live --host 0.0.0.0 --duration 1800
```

同一可信任區網的手機開啟 `http://C4的IP:8766`。HTTP 服務僅供區網觀察，不應轉發到網際網路。
不指定 `--host` 時只監聽本機 `127.0.0.1`。按 Ctrl+C 可停止，預設觀察 300 秒。
`--duration` 可明確指定，最多 86400 秒；沒有自動常駐或開機啟動。
可加 `--output /data/media/0/centering-session.jsonl` 保存診斷；已有同名檔案會拒絕覆寫。
頁面保留最近 600 筆診斷，有斷線與資料過期標示；停用觀察器不影響車控。

**本版尚未在使用者 C4 實測負載、原生訊息訂閱或 HUD 顯示；網頁不是原生 HUD 整合。**
如果未安裝本研究分支，原分支不會自動出現上述模組。

## 可評估條件與限制

兩側內車道線機率至少 0.7、std 不高於 0.3 m；法向估計寬度 2.5–4.5 m、前方寬度變動不高於 0.7 m。
至少 10 m 有效共同距離。自動轉向啟用、車速至少 18 km/h、沒有駕駛方向盤/油門/煞車介入。
變道、方向燈或模型轉彎意圖排除；結束後等待至少 2 秒，再累積 1 秒連續可信幾何。
車道跳變或訊息中斷會清除穩定時間。這些是研究篩選值，不是經驗證的安全界線。

排除畫面仍可查看，不會被混進一般過彎評估，也不會自動學成駕駛偏好。
持續 0.5 秒、超過 20 cm 的MPC 輸入路徑偏差僅列為「人工核對候選」。
20 cm 只是候選篩選門檻，不把 ±20 cm 定義為置中；小於門檻的固定偏移仍需核對。
車道線也可能同時辨識錯誤；同源模型比較不能證明真實置中。
側向加速度追蹤差與輸出飽和僅是線索，不能單憑一個畫面決定扭力或延遲參數。
模型標示 approach/curve/exit 只依局部彎曲趨勢，尚未經逐彎人工標註驗證。

## 驗證與後續接入

```bash
python3 -m pytest -o addopts='' --confcutdir=openpilot/tools/curve_centering openpilot/tools/curve_centering/tests -q
```

包含左右彎鏡像、不同車道格點、無外推、精確時間匹配、失效/過期訊息、駕駛介入、
變道收尾、幾何跳變、實際 cereal schema、損壞檔案及網頁資料逸出測試。

下一階段必須用同步影片核對「辨識中心是否正確」，再區分原始模型、路徑合成、
MPC 和車輛反應。候選修正需以左右彎置中誤差、邊界餘量、方向修正振盪及接管事件比較；
固定輸入回放後還需閉迴路模擬和受控場地驗證。未完成前不宣稱過彎已改善。
研究分支不合併到長期測試分支或正式分支，不操作車輛；後續控制改動另行審核。

參考：hoya/c3-atune 的 Log 分析與回復流程概念；未搬入其固定參數建議、AI 金鑰保存，
或手動介入後的橫向恢復改動。

## 離線模型控制基準

`model_baseline.model_step` 重現事件版本非 VW 模型模式的單次 100 Hz
曲率平滑與限幅，分開回報變化率限制和原本的 `curvature_limited`。
輸入必須是該控制步實際消費的數值；20 Hz 模型／規劃列不能代替完整
100 Hz 控制序列。`lateral_started` 是程序存續期間的旗標，不能直接
用前一筆 latActive 代替。未實作的車道線／VW 模式會明確拒絕。

目前只有與來源函式對照的數值測試；尚未完成 rlog 控制步輸入配對、
B 車道線模式及 C 混合候選，也不是行車表現驗證。

## 逐步控制稽核

```bash
python -m openpilot.tools.curve_centering.control_audit /private/segment17-rlog.zst /private/segment18-rlog.zst /private/segment19-rlog.zst --output /private/control-audit.json
```

限定已檢查的 Ioniq 5 與事件版本；其他版本明確拒絕，須先比對程式後
再擴充。完整解碼後才輸出，損壞檔不接受。輸出保留輸入 SHA256、
每步排除原因、模型時間戳、來源年齡、接管、曲率與導航狀態。輸出
只留私人位置，不將完整 JSON 或原始紀錄提交公開儲存庫。

此版本 `controlsState.lateralPlanMonoTime` 實際是使用的 modelV2
時間戳；工具精確配對該模型，而不是選最近模型。controlsState 與
carControl 須相隔不超過 5ms 且要求曲率相同，前次控制須間隔 5–15ms。
車速與 liveParameters 仍取之前最新值，限制年齡為 30ms／200ms，
不宣稱所有輸入都精確配對。模型年齡不超過 200ms。

重算每一步均使用紀錄中的前次指令，因此結果不是自由演進的控制
回放或閉環模擬；小誤差也不證明置中或安全。接管樣本保留做診斷，
不能用於宣稱無人介入的改善；torque 是要求值，不是實際 CAN 扭力。
