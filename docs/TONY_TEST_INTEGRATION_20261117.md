# Tony 與長期 Test 分支整合（2026-11-17）

分支：`test/tony-carrot-wip-integrated-20261117`。這是獨立整合候選分支；未部署、切換或操作任何車輛、C4 或 Mac。

## 來源與歷史

- 第一父提交：`Tony/carrot-wip`，`2d0d8d152503dfe7209afa1b353f54a570592e34`。
- 第二父提交：`test/carrot-wip-upstream-20261104`，`4a9fb70b1330e3148d6c0930827c70825e17a85e`。
- 共同祖先：`f89f40a37965b8a75f6a313e879cee02d8cff610`。
- 相對共同祖先，Tony 有 86 個、Test 有 176 個提交，包含各自的合併提交。使用雙父合併保留完整歷史。
- 原 Test、Tony 鏡像及其他駕駛分支不變。Tony 原有追蹤排程仍只更新純鏡像；此整合分支未加入自動合併排程。

## 整合決策

處理 21 個文字衝突檔案，保留兩邊非衝突更新。Tony 的低速轉向餘量、學習狀態、導航收藏、繁體中文與 FormosaLink，與 Test 的導航分享、外部導航優先、彎道／OSM／縱向預調速、HUD、LED、卡車觀察、SPAS、Jetlink 等既有變更共同保留。

- 設定清單取兩邊參數聯集，共 222 項；補上 Test 新增項目的繁體標籤。重新產生四語設定文件，保留 MANUAL 內容。
- 導航維持 Test 停用付費地址搜尋的決策，舊搜尋 API 回傳 410。Tony 收藏支援直接輸入經緯度，不呼叫永久地理編碼；Google Maps 分享路徑保留。
- 直接座標維持 Test 的持久目的地；收藏啟用維持 Tony 的本次行程暫存目的地。新增目的地會清除先前暫存目的地，避免優先級遮蔽；結束導航清除兩者。
- 管理程序同時保留 FormosaLink、Test 的 LED／OSM／卡車程序，以及 comma Connect 條件啟用。
- 保留兩邊 CI 工作並新增本分支限定的離線檢查。重新建置 web 產物，未手改壓縮檔。
- 離線測試包裝器只補齊真實 Cap'n Proto 訊息建立函式與明確預設值；IPC 仍禁止，未更動車輛控制或 Panda 安全邏輯來遷就測試。

## 已完成的離線檢查

Linux / Python 3.12；原生 CAN、radar motion、UI CPU 測試庫及 safety test hook 編譯成功。可重跑 `bash tools/integration_checks/tony_test_20261117.sh`（先依工作流程安裝依賴與編譯）。

| 範圍 | 結果 |
|---|---:|
| 彎道、OSM、路線曲率、縱向預調速／解除 | 388 通過 |
| 導航／收藏／Google 分享、外部導航優先、雷達、SPAS | 611 通過，另 34 subtests |
| CAN-FD 停車／按鍵、安全與控制故障檢查 | 316 通過 |
| Tony 低速轉向、ACAN 車道、HDA2 雷達、Sorento | 68 通過 |
| 學習狀態與橫向幾何傳遞 | 17 通過 |
| 前端導航、設定與繁體中文 | 302 通過 |
| 設定文件產生／驗證 | 34 通過 |

合計 1,736 個測試通過，另有 34 個 subtests。這是所列範圍的離線結果，不代表全套測試、完整裝置建置或實車驗證通過。

## 已知繼承問題與限制

1. 廣泛舊 `opendbc_repo/opendbc/safety/tests/test_hyundai_canfd.py`：本分支為 **325 失敗、353 通過、245 略過**。另建立原 Test SHA 的乾淨工作樹，重新編譯原生庫重跑，同樣 **325／353／245**；兩次失敗案例清單相同。安全程式及該測試檔與 Test 相同。失敗包含扭矩、按鍵、轉送及控制啟用預期，尚未調和舊測試與現有分支行為，不能據此宣稱安全驗證通過。
2. `clearance_shadow/tests/test_replay.py::test_observer_has_no_control_transport_or_runtime_integration` 仍不通過：舊靜態斷言禁止所有 `put_bool`，但現有 `live_observer.py` 包含既有命令列開關。整個 clearance_shadow 目錄與 Test 相同；保留原碼及失敗，未刪測試以取得綠燈。
3. 舊 `test_latcontrol_torque_buffer.py` 匯入已不存在的 `LAT_ACCEL_REQUEST_BUFFER_SECONDS`，無法收集；Tony 與 Test 原碼皆有同樣不一致。此過時測試未納入集中檢查。
4. 未做完整車機映像建置、實車行車或車輛 CAN 傳送；不得把分支建立成功、集中 CI 通過與實車可用畫上等號。

GitHub Actions 的遠端結果請以本分支實際執行頁面為準；上表是本次本機離線結果。
