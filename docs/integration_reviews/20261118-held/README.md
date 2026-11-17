# 融合更新暫停紀錄 — 2026-11-18（台灣時間）

狀態：HOLD，禁止推進融合目標或安裝部署。本候選保存已處理文字衝突的官方中間版本與 Tony 衝突證據，**尚未完成 Tony 整合或驗證**。

## 固定來源
- 官方：b5df7d4d3e014ba671e2a67b148c5431c0fab8b9（1 個未納入提交）
- Tony：b77f4702eebd8770f600608680f10623838d9b57（15 個未納入提交）
- 融合基準：e8990f3963b13a016bc983ec78ba9b4469fa5f14
- 本機官方中間合併：78c92e2c38bdd9ec614c5074588a5093f17d10aa
- 目標：test/tony-carrot-wip-integrated-20261117

## 阻擋原因：安全參數位元衝突
Test 已有 CANFD_BLINKER_KICK = 32768；Tony 新增 CANFD_ANGLE_CONTROL = 32768。
合併後 interface.py 分別設定這兩個旗標，而 Panda 同時用同一位元判斷 Kick 與角度控制：
- safety_hyundai_canfd.h：HYUNDAI_PARAM_CANFD_BLINKER_KICK = 32768，搭配 camera-SCC / SPAS 條件啟用 Kick。
- safety_hyundai_canfd_steering.h：hyundai_canfd_angle_control = GET_FLAG(param, 32768)。
- car.capnp：safetyParam 是 UInt16；現有旗標已占用所有 16 個單一位元，不能直接改成 65536。

這是控制協定語意衝突，不能把兩個 enum 名稱都留下就視為解決。需先設計不混淆且與主機/Panda 相容的配置，並測試 Kick-only、angle-only、兩者關閉、相關 camera-SCC/SPAS 組合及重啟/舊韌體相容性；不得關掉安全檢查繞過。

其他文字衝突共 14 個檔案，含導航（付費搜尋停用與手動座標須保留）、Cockpit、翻譯與生成產物。附件保存非生成檔的衝突差異。高德預調速的最新修正保留於基準。

## 本輪實際驗證
執行 tools/integration_checks/tony_test_20261117.sh：
- 第一組彎道相關測試：388 passed。
- 第二組收集即中止：test_navigation_map.py / test_google_share.py 因 navigation.py 未解衝突標記產生 IndentationError；exit 2。
- 這是未完成合併造成的阻擋，不是既有測試失敗，也不構成回歸通過。
- 完整 CAN-FD 基準/候選比對、產物重建與候選 CI 尚未執行；不引用 Tony 自述結果當作本融合版本的驗證。
- 未更新目標分支、未刪測試、未調低安全限制、未操作車輛/C4/Mac或發佈 APK/服務。

## 繼續處理
此遠端候選是官方中間版本加審查證據；Tony 的未解合併仍保留於本機 sync/tony-integrated-20261118-0006。
以此候選 checkout 後執行 git merge --no-ff --no-commit b77f4702eebd8770f600608680f10623838d9b57，可重現 Tony 合併衝突（文件新增不影響程式衝突）。
解決安全配置後，需完成所有功能保留審查、指定腳本、相關新增回歸、完整 CAN-FD 與實際基準比較、重建及 CI，再讀三個最新 SHA；目標有並行更新時重新整合。成功才用非強制且 expected SHA 保護更新目標。
