# 導航路線與視覺彎速整合：測試修正版

原始基底：`FANHAOHSIANG/openpilot-carrot`，`204f9cca`。
整合分支：`test/truck-clearance-204f9cca`，在 `cde5315b` 的卡車功能與開關修正之上加入。
狀態：程式已接入速度選擇、完成離線驗證；尚未安裝 C4，也沒有實車成效證據。

## 已實作

- 沿用既有導航路線來源，使用實際 WGS84 經緯度，不從投屏畫面猜路。
- GPS 位置、行進方向及模型前方約 10–60 公尺的路徑重合後，連續確認至少 0.3 秒。
- 依圖資可用範圍預覽最多 500 公尺，以曲率、剩餘距離和減速反應時間計算速度上限。
- 模式 2 不再以 TBT 提示的 ±500 公尺範圍限制路線彎速；路線中的彎道與下一個轉彎提示可以是不同位置。
- 彎度放緩後逐步解除路線限速，每秒上限增加最多 3.6 km/h；這是上限變化，不是直接下達加速命令。
- 模式 2 仍選較低的視覺彎速，原本速限、跟車規劃、油門接管與縱向加速度限制保持原流程。
- GPS／模型過期、不同分岔、位置跳躍、路線交叉難以判別或座標太稀疏時，不產生新的路線限速。
- 已經生效的路線限速在資料失效時短暫維持，再逐步解除；不會把「沒有路線」誤當成新彎道。

`AutoCurveSpeedFactor` 提供曲率速度的橫向加速度預算；`MapTurnSpeedFactor` 與最低彎速先套在彎道目標，再計算進彎距離速度上限。保留既有可調範圍與模式 0／1 停用路線計算結果的行為。

## 實際使用前提

本功能使用 `TurnSpeedControlMode=2`，且 C4 必須收到當前導航來源的路線座標。
Carrot 自己依座標目的地計算出的 Mapbox 路線，或外部導航送來的 polyline 均可作為輸入。
外部導航連線仍有最高來源優先權；沒有 polyline 的外部連線不會借用另一條儲存的 Mapbox 路線。
使用 C4 自己規劃的路線時，要讓它成為現行導航來源，而非同時被外部導航連線占用。

檢查已提供的 `Copilot-tw-wide.31-full-frame-source.zip`：其中 Google 模式明確只有投屏，
並會清除高德 `route` 與導航欄位；該原始碼包沒有 Google 路線座標提取實作。
因此這份 C4 修正不代表 Google 投屏已能送出路線，也不代表缺少 polyline 的舊記錄能重新算出導航彎度。
這次未更改 CP APK、導航 API 金鑰或導航服務計費設定。

## 如何判斷有沒有參與

`carrotMan.szPosRoadName` 的診斷尾碼 `rc=` 會留下狀態；原本的 `desiredSource` 會繼續表示最後勝出的速度來源。

| 診斷 | 意義 |
| --- | --- |
| `matched` | 目前路線、位置和近端視覺路徑吻合；附目標彎道距離、彎速與配對誤差 |
| `confirming` | 等待不同模型影格的連續確認 |
| `no_route` | 沒有有效路線座標 |
| `stale_position` / `stale_model` | 定位或模型資料過期 |
| `model_mismatch` / `off_route` | 視覺路徑或位置方向不吻合 |
| `ambiguous_route` / `position_jump` | 路線分段難以判定或定位進度異常 |
| `coarse_route` / `short_route` | 路線座標不足以可靠計算曲率 |

`matched` 不一定代表路線正在主導車速；若視覺或其他來源要求更慢，最後來源仍會是 `vturn`、`road` 等。

## 驗證結果與界線

51 項曲線及整合測試通過，涵蓋左右彎、座標正負方向、超過視覺距離的彎道、連續開彎速度恢復、
新彎再次收緊、資料中斷、重新規劃、重複影格、錯誤路口、距離很遠的 TBT、模式開關與較低速度來源優先。
整合測試執行完整的正式 `CarrotMan.carrot_navi_route` 與 `CarrotServ` 方法，使用真實 cereal 訊息，
隔離 IPC、設定儲存與程序啟動；不是 C4 完整建置或實車測試。

合成案例：前方約 210 公尺、半徑約 80 公尺的彎道，車速 90 km/h、兩個比例均 100%、最低彎速 30 km/h。
計算彎道目標約 44.46 km/h，當下進彎上限約 79.79 km/h。此數值僅驗證距離計算，並非使用者第 16 段的實測重播結果。
最大 4096 點路線的桌面 2000 次計算中，時間中位數約 0.48 ms、P99 約 0.90 ms；不能等同 C4 效能。

新增程式通過 Ruff，修改的服務檔通過語法與未定義名稱檢查。
英文／韓文設定說明與目錄已同步；4 份 Wiki 說明本機驗證通過，Wiki 工具 25 項測試通過。
新增 GitHub 檢查工作流程，推送本分支後會執行；實際結果以對應提交的 Actions 紀錄為準。

重跑離線測試（需 numpy、pytest、pycapnp）：

```sh
PYTHONPATH=. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest \
  --confcutdir=openpilot/selfdrive/carrot/tests -c /dev/null \
  openpilot/selfdrive/carrot/tests/test_route_curve.py \
  openpilot/selfdrive/carrot/tests/test_route_curve_integration.py \
  openpilot/selfdrive/carrot/tests/test_curve_speed.py -q
```

本次修改不包含先前另外討論的下一個 TBT 距離換算修正，也不改動模型、轉向、CAN、AEB 或 FCA。
此修正已整合在上述卡車測試分支的程式碼；裝置更新與實車效果仍需另外驗證。
