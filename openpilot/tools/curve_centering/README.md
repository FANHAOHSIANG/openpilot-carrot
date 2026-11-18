# Carrot 過彎置中研究台 v0.1

目標是找出左右彎偏離中央的來源，讓後續路徑或轉向修正有可重現的依據。
本版提供即時只讀監看、離線 rlog 分析、繁體中文回放頁與結構化 JSON。
**沒有自動調參、候選致動輸出或新訓練的駕駛模型，也沒有修改既有規劃器。**
獨立整合分支另有預設關閉的實際 controlsd 只讀影子接線，詳見文末最新章節；
它不把候選送入轉向或控速。

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


## Offline relative-centering candidate (experimental C component)

`centering_shadow.py` compares the recorded **model action** with an unactuated
proposal. It is not the final A/B/C control comparator: lane baseline B and
100 Hz candidate limit replay are still pending. Never call this a vehicle
command or use it as an installable control implementation.

```bash
python -m openpilot.tools.curve_centering.replay local-rlog.zst --output /tmp/observer
python -m openpilot.tools.curve_centering.centering_shadow /tmp/observer/centering.json --output /tmp/candidate.json
```

Use complete chronological input per drive; independent files reset observer
warmup. Missing action, feedback, geometry or mode information is not fabricated.
The candidate additionally requires one continuous second of eligible samples,
model mode, unsaturated steering and estimated acceleration tracking error at
most 0.2 m/s². It compares model position to the same model's lane midpoint at
20 m, with right-positive geometry and curvature. Positive path error asks for
negative curvature adjustment. The small-angle proxy is `delta_k * 20² / 2`;
it is NOT a simulated future position or measured clearance.

Experimental settings bound additional lateral acceleration to 0.25 m/s² and
its normal slew to 0.25 m/s³. Low speed (<5 m/s), invalid/missing action or time,
manual intervention and maneuver states discard the unactuated proposal
immediately. Geometry/quality/tracking loss slews the correction toward zero;
re-entry requires stable data again. Immediate discard is NOT a demonstrated
smooth actuator handover. At low speed the acceleration bound permits a larger
geometric proxy; these constants are not driving recommendations.

This prototype does not infer body center, apply PathOffset, learn driver
preferences, or bypass existing steering protection. Body calibration remains a
separate blocker. The optional runtime shadow tap imports this module for observation only; production commands never use its proposal. Before considering a
controller candidate, replay the original 100 Hz smoothing/curvature/rate limits,
verify handover continuity, and evaluate a closed-loop vehicle model with camera
bias, actuator delay, saturation and missing-line sweeps. The current same-input
replay cannot establish that the car will actually become more centered.

## Synthetic closed-loop falsification and uncertainty experiment

Run `python -m openpilot.tools.curve_centering.simulation --output /tmp/curve-simulation.json`.
CI runs the same command and retains the synthetic results as an artifact.
This reconstructs an auditable harness from the interrupted research, not the
unavailable original scratch files. Its v2 counts must not be mixed with the
earlier 128-case sweep.

A is an analytic preview-driver surrogate through the pinned 100 Hz model
limits; C adds the existing shadow proposal; U adds a conservative error interval.
They evolve separate poses through a Frenet kinematic plant with delay, lag and
an assumed 3 m/s² actuator ceiling. No neural model, actual EPS, tire forces,
banking, longitudinal policy or recorded-route reconstruction is present.
The 320 scenarios include mirror bends, error-bound violations, line loss,
stale data, takeover and deliberately infeasible demand. Three U gains are
experimental settings, not a selected optimum. B lane mode remains missing.

`UncertaintyShadow` accepts an explicit, time-bounded `GeometryBound` for
differential model-path/lane geometry error. If the interval includes zero,
its target correction is zero; missing, expired or mismatched assumptions
withdraw with the existing decay and stable reentry. Driver and maneuver
gates still discard the unactuated proposal. The original C defaults are unchanged.

A common translation of camera coordinates cancels in relative path-minus-lane
geometry. The injected differential error therefore must NOT be described as a
measured camera/body offset, or used to explain the user's real incident.
The bound supplied in simulation is an assumption. There is no automatically
trusted bound from rlogs, PathOffset, user preference or same-model agreement.
Independent labels and body calibration remain required before physical use.

RMS deterioration >0.02 m OR peak deterioration >0.05 m marks a synthetic
regression. Invalid plant-domain runs are excluded from valid comparisons and
reported separately, never counted as passes. Lower RMS can coexist with a
peak regression. Results within and outside the assumed bound are separated.
A green software CI means the harness and guards behave as tested; the report
always has `deployment_approved=false`. The optional runtime shadow imports the original C proposal for observation; no production command uses either
proposal or simulator, and no installable vehicle fix is claimed.

## Offline entry-speed feasibility

`speed_feasibility.preview_speed_limit` accepts explicit upper curvature bounds
at forward distances, a chosen lateral-acceleration budget, braking deceleration
and latency. It computes the hypothetical present-speed limit needed to reach
each future curve cap after reaction delay. There is no default vehicle capability,
no map trust assumption and no vehicle-control hookup. It does not model jerk,
friction, banking or hazards, and cannot guarantee safety beyond the supplied preview.
Raw model action is not independently measured road curvature.

The low-gain U sweep's 12 covered-bound regressions all have 18 m/s and 0.01 /m:
demand 3.24 m/s² exceeds the toy plant's 3.0 m/s² authority. Original A also has
roughly 9.3–9.4 m peak displacement in these cases. Their numerical domain was
valid; that must not be mistaken for lane keeping. The simulator now separately
reports boundary exceedance against an explicitly assumed 0.85 m half-clearance.
No user vehicle width or real lane measurement is inferred from that number.

For illustration only, a 2.4 m/s² budget and 0.01 /m curve bound imply
sqrt(2.4/0.01) = 15.49 m/s (55.77 km/h) at the curve. This is not a speed
recommendation for the user's interchange. Integration of longitudinal dynamics
and uncertain preview remains pending; this function alone does not establish
that deceleration happened early enough in the real recordings.

## 獨立分支：可執行的隔離控制接線（2026-11-17）

本節描述 `test/carrot-pr52-integration-20261117` 的新增介面。已接通的是：
**Observer 輸出 → 每個控制步的防護 → C 候選 → 此分支實際曲率選擇／平滑／限幅
程式 → 記憶體中的比較輸出**。不是只列出候選修正量；可以看到限幅後的差異與退出殘留。
本段為 fb59c77e 的隔離介面；後續已新增 controlsd 只讀接線，見下一節。
候選仍沒有接到 LaC 扭力／角度控制器、carControl 發布或 CAN。
車上安裝這個分支不會啟用過彎修正；沒有新增 Params、車機選項或開機程序。

`source_control.py` 校驗 `controlsd.py`、`drive_helpers.py` 的完整 Git blob 雜湊，
只抽取經核對的純量程式敘述，在沒有 Params／messaging 的 namespace 執行。
執行的是實際首次橫向啟用處理、模式選擇、模型曲率平滑及 `clip_curvature`，
不是再複製一份公式作為「已接線」證據。來源變動會拒絕執行，需重新審查及驗證 pin。
這仍不涵蓋完整 Controls 程序、原生車輛模型、扭力控制器或 Panda 安全檢查。

Python 3.12，從儲存庫根目錄執行；先在桌面環境準備依賴：

```bash
python -m pip install pycapnp==2.1.0 zstandard pytest numpy ruff==0.17.5
# 自造 35 秒、3500 步資料，經真正 Observer，注入 14 種故障；目錄必須尚未存在
python -m openpilot.tools.curve_centering.bridge_demo --output /tmp/curve-bridge-demo
# 預設 shadow：選出基準輸出，候選只作比較
python -m openpilot.tools.curve_centering.control_bridge /tmp/curve-bridge-demo/inputs.jsonl \
  --output /tmp/curve-shadow.jsonl
# 明確選 isolated：候選送到本機結果檔／記憶體，仍無任何致動介面
python -m openpilot.tools.curve_centering.control_bridge /tmp/curve-bridge-demo/inputs.jsonl \
  --mode isolated --output /tmp/curve-isolated.jsonl
```

這些命令準備完依賴後可斷網執行，不需 C4 或私人 rlog。輸出檔也必須尚未存在。
`summary.json` 顯示防護原因與殘留差異；`results.jsonl` 逐步保留兩種模式。
`selected_curvature` 只是離線試驗選出的純量，`vehicle_output` 與
`deployment_approved` 永遠為 false。示範是固定合成輸入，不是閉迴路車輛模擬。
原來 `simulation` 與 `spatial-ramp.mjs` 是分開的否證工具，仍須執行並查看負面結果。

自備桌面測試介面可使用 `ControlBridge.step(ControlTick(...), observation)`。
JSONL 每行為 `{"tick": {...}, "observation": {...}}`，完整欄位見
`ControlTick` 及示範的 `inputs.jsonl`。時間全部是同一單調時鐘的整數奈秒。
observation envelope 含 `model_ns`（確切消費的模型 ID）、`available_ns`
（Observer 輸出可取得時間）、完整 `row`；同一模型重複使用時內容不得改變。
不能拿較晚才完成的 lateralPlan 結果回填更早的控制步。
`lat_active` 須由測試端提供已完成原生許可／故障判定的結果，不能把模型或 observer
eligible 當成啟用許可。此工具不從歷史日誌猜測這個結果；也不將 20 Hz 報告冒充
完整 100 Hz 消費輸入。未知輸入必須標為未知，不要填 false 來通過防護。

防護與啟用條件：

- 預設 shadow；只有明確選 isolated 才在本機結果中選候選。兩者都沒有車輛輸出。
- 每次呼叫重查駕駛方向盤／油門／煞車介入、變道／方向燈意圖、latActive、
  飽和、既有安全限幅、低速。布林欄位必須明確，缺失／未知不當成通過。
- 模型與 liveParameters 最長 200 ms、carState 最長 30 ms；控制間距須為
  5–15 ms。模型 ID、action、Observer 時間須對上，未來資料不可用。
- 使用生產模式選擇式；`useLaneLines` 單獨不代表實際使用車道模式。
  真正車道模式或 VW MEB 會停止純量試驗，回傳 null，沒有假造這些模式的 fallback。
- Observer 必須已通過自身幾何／時間／意圖防護，20 m 相對幾何有效、追蹤誤差
  不超過既有候選門檻，且再次連續穩定一秒。同一模型重複控制步不累加穩定時間。
- 任何防護失敗立即撤回新修正並重置候選穩定時間；重新進入須重新累積。
  當前速度用於將候選加速度修正轉成曲率。既有生產平滑／限幅仍在其後執行。
- 無法計算基準時 `selected_curvature=null`，表示試驗中斷，**不是零曲率的車控指令**。

**尚未接入車輛致動的具體原因：** C 候選已有越界／退化案例，沒有獨立車身中心
或道路真值；同模型幾何不等於實際置中。撤回修正後的平滑殘留被明確記為
`residual_curvature`，不把立即撤回注入量稱為無擾交接。低 gain、誤差界限內且
名義可行的 96 案仍有 24 案超過假設餘量；另一空間右彎仍有 0.867 m > 0.85 m。
U 的假設誤差界限沒有冒充量測值，這個 bridge 只串接原始 C 候選。
尚需獨立幾何校驗、經校準且耦合縱橫向的閉迴路測試、完整原生控制鏈與退出／重入
驗證，才能重新評估是否適合接入致動。這份交付不提供上路測試流程。

## 實際 controlsd 只讀影子接線與失敗歸因（歷史執行緒版本）

**最新實作已改為獨立子程序，請見 [PROCESS_ISOLATION.md](PROCESS_ISOLATION.md)。**
以下保留舊執行緒架構及負面證據；目前控制端只送128-byte非阻塞資料，
幾何配對與分析在子程序。桌面負載改善已驗證，C4時序未驗證，預設仍關閉。

這次不再只有 CLI：`Controls.state_control()` 完成原有啟用判定、曲率限制、
LaC 與有限值檢查後，新增只讀觀察點。它取得**實際消費的**前次曲率、
process-lifetime lateral_started、VM 回授、採用的 roll、模式與當次 actuator
curvature；工作執行緒用這些資料核對 A 基準及 C 假設輸出。
**仍沒有把 C 輸出寫回任何 actuator 或 desired_curvature。原本車控沒有新增致動模式。**

此入口只有在建立 Controls 程序時明確設定環境變數 `CURVE_CENTERING_SHADOW=1`
才建立，未設定時不載入研究模組、不啟動工作執行緒。它不是 Params 或 UI 開關，
也不由 manager／啟動腳本自動設定。這是給具備原生依賴的桌面／受控控制程序測試端的
觀察入口，尚未通過 C4 負載資格；本文件不提供車輛安裝或行駛操作步驟。

觀察點只複製需要的欄位，幾何陣列最多64點／4條線，不擷取 GPS、VIN 或路線識別。
容量4的佇列不等待可用空間；滿載時丟棄並換代，使積壓證據失效，下一份接受資料
重新帶入模型與規劃資料並重新穩定。分析和每秒最多一次的
`curve_centering_shadow` cloudlog 診斷在工作執行緒處理，內含：

- `actual_baseline_error`：以實際前次狀態重算 A，與當次實際曲率的差。
- `policy_delta_curvature`：C 與**同一前次 C 狀態**下原政策的差，辨識當步新增修正。
- `history_delta_curvature`：不同歷史狀態下的 A/C 差，不當成當步新增修正。
- `reasons`、丟棄數與擷取耗時。資料缺失／模式不支援時差異可能為 null，不能當成通過。

觀察器或診斷輸出例外只會停止觀察，不得壓掉、替代或更動既有控制輸出。工作執行緒
仍與 Python GIL／排程共享資源；有界佇列不等於硬即時保證。桌面首輪3000次擷取
中位19.2 µs、P95 68.4 µs，但最大13.255 ms；這個尖峰保留為負面負載證據。
另輪同時量測 wall/thread CPU 的3000次最大0.339 ms，不能用重跑較好結果抹掉前輪。
原生 C4 的端到端時限、排程競爭與關閉恢復仍待驗證，保持預設關閉。

桌面可先執行實際控制方法與只讀觀察點回歸，不需車輛或私人資料：

```bash
python -m pytest -o addopts='' --confcutdir=openpilot/tools/curve_centering \
  openpilot/tools/curve_centering/tests/test_runtime_shadow.py -q
python -m openpilot.tools.curve_centering.simulation --output /tmp/curve-sweep.json
python -m openpilot.tools.curve_centering.failure_analysis /tmp/curve-sweep.json \
  --output /tmp/curve-failures.json
node openpilot/tools/curve_centering/spatial-diagnostics.mjs
```

`test_runtime_shadow` 執行整個生產 `state_control` 方法，保留原生 cereal 資料型別，
但替代硬體／IPC、VM／LaC／LoC 等依賴；不是完整原生控制驗證。
原方法移除新增觀察敘述後的 AST 雜湊必須與 fb59c77e 一致，再比對所有 CarControl
欄位及狀態。先前缺少的 params_pyx／acados 已補齊，13項原生扭矩啟動測試已通過；詳見 VALIDATION。

### 三類否定結果應如何解讀

1. **0.867 m 空間匝道**完全沒有 C/U 候選。原代理駕駛在偏差0.3 m、傳遞延遲0.3 s、
   致動滯後0.15 s及平滑0.1 s下，出彎42個步驟超過原0.85 m假設。峰值時已在反向修正，
   當步未達3 m/s²致動上限；不能簡化成「這時沒有轉向能力」。零偏差／零傳遞延遲
   探針可消除此合成越界，並不代表真車可消除偏差／延遲。用已知玩具模型延遲總和
   做 oracle 道路預覽，峰值可降至0.426 m；真實道路預覽與延遲均未獲證，因此沒有
   把這個只在合成資料成立的先知修法接到車控。
2. **24/96 案**是同一組原基準 A、C、低增益U均越界，全部具0.3 s傳遞延遲與0.3 m
   代理模型偏差。候選沒有新增越界案例，但這不等於候選無害：C仍有 **33/96 相對退化**，
   低增益U為0/96（兩者此子集皆無數值無效配對）。C在此子集最大額外
   峰值0.05857 m，U為0.01181 m。原0.85 m門檻、案例及所有相對退化仍保留。
3. **212個退出殘留步驟**的同狀態政策差異全部為0；不同歷史狀態的差按既有
   `exp(-0.01/0.1)` 衰減，並非212次新注入。第一步仍有約0.226 m/s²假設加速度差，
   所以不能說物理影響為零。直接重置到另一個基準狀態會產生約25 m/s³跳變，
   超過原5 m/s³變化率限制，沒有採用這種掩蓋殘留的修法。實際LaC、駕駛接管與EPS
   如何消化這段歷史仍缺原生／校準閉迴路證據。

這輪修正的是時間可用性檢查（規劃發布可早於實際消費時間，仍禁止未來資料）、
退出歸因與真實消費點的只讀接線，**不是宣稱舊越界已解決**。
要接入致動，至少還需獨立道路／車身標籤與可信幾何符號、實際模型執行身分及延遲、
含LaC/EPS及縱橫耦合的校準閉迴路、原生退出／重入及最壞時限證據。

### Offline refinement R and the 33 regressions

`refined_shadow.py` adds an explicit experimental R arm; it does not replace C,
U, the live shadow tap, or any production controller. R uses U's existing 0.25
gain and nearest-zero differential-error interval, and withdraws the proposal
immediately when evidence, geometry, tracking, mode or saturation quality fails.
It preserves the downstream production smoothing and rate limits; proposal
withdrawal is not proof of safe physical handover. A fresh valid interval and
warmup are required for reentry. No calibrated vehicle interval is supplied.

32 of the 33 original feasible/covered C regressions have zero model bias and
+/-0.2 m differential geometry error. In this synthetic driver, the raw geometry
algebraically reduces to `model_bias + differential_error`, independent of the
vehicle pose. C therefore steers against error rather than a true bias. Changing
only differential error to zero eliminates all 32 regressions. The remaining
case has bias 0.3, delay 0.3, positive turn and stale fault: C improves RMS but
increases peak by 0.058566 m. The same full-gain correction without that fault
reduces peak by 0.032618 m, demonstrating a fault/history interaction. Either
interval shrinkage or lower gain removes that case's regression; an immediate
proposal reset alone is not established as a physical cure.

R has 0/96 regressions on the same feasible/covered subset (C still has 33/96),
but **24/96 still exceed the assumed lane margin**. Across all 320 original
scenarios, R has 16 regressions among valid pairs and 28 invalid plant trajectories;
200 cases exceed the assumed margin or leave the plant domain. These failures
remain in the report, including deliberately violated interval assumptions and
insufficient actuator authority. This is development-set evidence, not held-out
road validation. The original 0.867 m spatial-ramp failure is unchanged; R is not
implemented in that separate model. No hypothetical road preview or latency
calibration is connected to vehicle control.

Reproduce with the same dependencies as above (choose new output paths):

```sh
python -m openpilot.tools.curve_centering.simulation --output original.json
python -m openpilot.tools.curve_centering.refinement_analysis original.json --output refinement.json
python -m pytest -o addopts='' --confcutdir=openpilot/tools/curve_centering openpilot/tools/curve_centering/tests -q
python -m ruff check openpilot/tools/curve_centering
node openpilot/tools/curve_centering/spatial-diagnostics.mjs > spatial-diagnostics.json
```

CI publishes `refinement-analysis.json` alongside the unchanged original sweep,
withdrawal analysis and spatial counterexample. A passing job means the tools
executed and invariants passed; it does not mean every simulated trajectory passed.

### 桌面完整程序時序驗證

六輪原生 IPC／完整 controlsd 關開對照與工作者例外結果，見 [PROCESS_BENCH.md](PROCESS_BENCH.md)。
正常與背景負載仍有發布超時，故**維持預設關閉**；沒有把影子模式改成 C4 預設啟用。
工具只啟動隔離的桌面合成程序，不部署車輛；原始資料下載沒有重試。
