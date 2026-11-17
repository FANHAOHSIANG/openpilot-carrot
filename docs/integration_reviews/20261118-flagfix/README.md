# 2026-11-18 融合候選：安全旗標衝突修復（HOLD）

**尚不可合併：新增傳統 CAN 邊界測試 2 項失敗。融合目標未更新。**

## 固定來源與範圍

- 融合基準：`e8990f3963b13a016bc983ec78ba9b4469fa5f14`
- 官方：`b5df7d4d3e014ba671e2a67b148c5431c0fab8b9`（1 個未納入提交）
- Tony：`4ff6cfb911c23fde84b1d5e8e1f2990cfb06ffc9`（18 個未納入提交）
- 目標：`test/tony-carrot-wip-integrated-20261117`

官方增加巡航各階段 wall/CPU 耗時診斷，保留 Test 的非同步設定快照、快照年齡及唯讀 offroad 保護。
Tony 包含 Cockpit 0.5 操作布局／辨識狀態、地圖共用、預設關閉的訓練資料貢獻與模型工作室、CAN-FD 轉向保護修復、低速需求跟隨及 HkgPhase1Assist。
HkgPhase1Assist 預設關閉；不更改指紋／HDA／轉向協定，原有 EPS/Panda、駕駛接管與資料新鮮度限制保留。未替使用者啟用功能。

## 安全旗標配置

原衝突為 Kick 與角度協定都使用 32768。此融合版本保留 Kick=32768，把 CAN-FD 的角度協定識別設為 512。
512 在傳統 Hyundai CAN 模式仍表示 ALT_LIMITS_2。盤點共用讀取與所有消費者後，確認其扭力限制消費者僅在 safety_hyundai.h；CAN-FD 呼叫共用初始化時明確遮掉 512，並由 CAN-FD 轉向檢查獨立讀取原參數。
主機旗標與 Panda 同步修改，沒有擴大 UInt16、放寬扭力／速率／駕駛讓步限制，也沒有刪除 Kick。

新增測試使用真正 C safety TX hooks，交叉涵蓋 Kick、angle、camera-SCC、SPAS 的 16 種組合與清除後重新初始化；驗證角度指令與 SPAS 封包不會互相授權，超額扭力仍拒絕。另測 CAN-FD 切回傳統 CAN 時的正負 170/171 邊界，但測試失敗：171 仍獲准發送。不能據此宣稱傳統 CAN 的扭力保護有效。
沿用正常啟動流程的精確韌體簽章驗證：若刷寫後仍不符，關閉裝置連線並拒絕繼續。新增測試使用假的 USB 裝置驗證相符、不相符及更新成功三條路徑；沒有存取實體硬體。
這不是可混用任意舊版 Panda 韌體的協定；部署時仍須依正常流程建置並驗證相符韌體。

## 保留客製

付費地址搜尋端點維持 410，config 明確回報 disabled；手動座標、Google 分享配對與最愛保留。Tony 舊 Google place-ID 最愛遷移改用明確輸入座標，不呼叫付費搜尋。
保留 Test 導航／OSM／彎道預調速（含 e8990f39 高德修正）、HUD／LED／卡車／SPAS／Jetlink。
Cockpit 導航按鈕開啟座標表單，並保留新版辨識設定、顯示比例、連線恢復與相機生命週期。
訓練資料貢獻須使用者另行明確同意；未配對、未同意、行車中不開始上傳，撤銷立即停止。工作室腳本、模型選擇與發佈流程僅納入原始碼，本次未執行部署、模型下載選用或發佈。

## 實際驗證

- 指定 integration script 全部通過：Python 2279 項、Wiki unittest 34 項、前端 372 項；另有 37 個 subtests。
- 上述執行後增加的傳統 CAN 邊界 2 項失敗；整個安全旗標檔實際為 16 passed / 2 failed。先前以後續 Node 命令成功狀態誤報整段成功，已更正。
- Vision／HUD／ONNX 額外回歸：117 項通過。
- CPU 原生函式庫與 C safety 函式庫已重建，網頁產物已重建；文件檢查通過。
- 完整 CAN-FD 用本輪實際基準 worktree 與候選比較：基準 325 failed / 353 passed / 245 skipped；候選 199 failed / 479 passed / 245 skipped。修復 126 項，新增失敗 0；逐項結果在 canfd-comparison.json。
- CI 44134879992：Panda F4/H7 編譯成功；整合腳本在新增安全檢查組以 2 failed / 280 passed 中止，後續步驟未執行。融合目標沒有更新。

整合過程曾發現並修復導航缺少 time import、測試 fixture 缺少融合分支設定欄位，以及前端生成檔未更新；沒有把這些新增失敗列為既有或移除測試。最愛遷移測試改為驗證使用者指定的無付費搜尋行為；Wiki 精確筆數同步新增設定（223 項），未降低驗證。

完整 CAN-FD 仍有 199 項失敗，不宣稱完整安全／實車／HIL／原生 MPC solver 閉迴路驗證通過。本次未操作或安裝到車輛、C4、Mac，未發佈 APK 或外部服務。

## 尚未解決的阻擋

`opendbc_repo/opendbc/safety/safety/safety_hyundai.h` 的傳統 CAN 轉向 TX 路徑呼叫 `steer_torque_cmd_checks`，但其違規分支仍是 `//tx = false;`。基準 e8990f39 也存在同一段程式；這項源碼比對僅解釋原因，**不把新增失敗改列既有而讓 CI 通過**。

保留新增兩項失敗測試及原斷言；不更改預期為允許超額扭力、不跳過或刪除測試、不取消安全限制。若進一步恢復傳統 CAN 的拒絕路徑，須對傳統 Hyundai 車型的控制器輸出、手動限制與原有安全套件另做完整相容性審查與實際基準比對，不能只取消註解就合併。

本輪已解決 CAN-FD 的旗標文字及語意衝突，但仍未達到使用者要求的合併條件。候選程式提交 a063c05bcc4f63293618846c2fcf294f5cc8fe91；失敗 CI：https://github.com/FANHAOHSIANG/openpilot-carrot/actions/runs/44134879992 。本紀錄更正不代表新的程式驗證。
