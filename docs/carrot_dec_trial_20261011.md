# carrotpilot DEC 實驗分支

基底為官方 `ajouatom/openpilot` 的 `carrot-wip` 提交
`c6925561478f8fc84e50fce4373c87b0dd075d4a`，分支為 `carrotpilot-dec`。

## 啟用與還原

安裝此分支後，開啟裝置的「實驗模式」，再到 Carrot Web 設定搜尋
`CarrotDEC`，開啟「動態實驗模式 (DEC)」。DEC 預設關閉，既有備份不會自動開啟。
設定約每秒讀取一次；在停車時修改。關閉 DEC 即恢復原 carrot-wip 模式選擇。
開啟 DEC 而未開實驗模式不會啟用 DEC。

## 行為

一般巡航選擇 ACC；輕微模型減速持續 0.25 秒才進入 blended。
模型要求停車、模型加速度 ≤−1.5 m/s² 或 Carrot 出發準備狀態立即進入 blended。
連續 2 秒沒有減速需求後回 ACC。減速判斷採模型加速度 ≤−0.5 m/s²，或
0.5–2 秒模型速度比實際車速低超過 max(2 m/s, 15%)；只看近程預測。

Carrot 已進入 e2eStop/e2eStopped 或 soft hold 時，優先使用 ACC 的停車障礙物，
包括既有 signal-assist 紅燈保持約束。無效或不完整資料、駕駛踩踏板、縱向未啟用時，
不新增 DEC 判斷，沿用既有模式並清除 DEC 歷史。

只改模式選擇，不改模型、雷達選擇、煞車限制或模型/MPC 的 min 混合公式。
前一份離線狀態接續補丁未合併，避免把兩種控制實驗混成同一項變更。
DEC 並非移植完整 sunnypilot DEC，門檻與停車約束是本分支的實驗實作。

## 驗證與限制

15 個 DEC 測試涵蓋巡航、短暫/持續模型波動、立即停車/强減速、2 秒遲滯、
停車保持優先、資料失效、接管、設定註冊及實際 planner 程式區塊整合。
整合測試替代服務物件及 MPC 輸出，不是原生 acados 或完整車輛閉迴路。
另檢查 Python 語法、設定生成器、Wiki Markdown 和韓/英文使用者文件映射。

尚未進行 C4 編譯/安裝、原生 MPC 回放、CAN 或實車驗證。
0.25 秒切入確認及 2 秒返回門檻尚未車輛校準；不能宣稱已解決速度波動或保證紅燈停車。
需要比較開/關 DEC 下的 aTarget、aTargetBase、模型 desiredAcceleration、
cruiseTarget、vTargetNow、xState、實際 aEgo，以及 `carrot_dec` 切換日誌。
確認加減速改善與必要煞車反應後才決定是否採用。

## 本機測試

```sh
python openpilot/selfdrive/controls/tests/test_carrot_dec.py
python -m py_compile openpilot/selfdrive/controls/lib/carrot_dec.py openpilot/selfdrive/controls/lib/longitudinal_planner.py
```

設定的韓/英詳細說明同步在 `docs/user`。中文說明在 Carrot Web 新增設定中。
既有設定 Wiki 生成器會依目錄生成三語設定說明；本分支不發布到官方 ajouatom Wiki。
