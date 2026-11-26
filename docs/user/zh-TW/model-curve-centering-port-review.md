# 模型彎道置中移植候選（僅離線審查）

基底 fc17546f5c870b7638e42221230d58e22d132ebf；原始實作 cc13575e；參考融合版 5eda71aad247220246bc8b662b6d5642e9c481fb。
只移植 IONIQ 5 的選用模型曲率修正、設定與診斷。預設關閉。保留獨立 Test 的 CarrotPlanner、既有模型 0.1 秒平滑與 clip_curvature；不改縱向控制、車控限制、CAN/Panda 或 HKG 扭力。獨立 Test schema 尚無 plannerProfile，因此不宣稱 Autospeed 相容。
開關、車道線模式、接管、方向燈、變道、導航轉彎、資料新鮮度、標定等拒絕條件沿用融合版。新增 schema 欄位使用融合版相同 ordinal；@68 為保留相容欄位。
本候選未執行完整 native CI、實車或離線真實路線回放；僅可作離線審查，不可部署。

首輪候選驗證：本地 33 項模型幾何單元測試通過（helper 與原測試 Git blob SHA 皆核對一致；使用固定 Test 的模型距離格點，並非完整執行環境）；GitHub 原有 native CAN-FD/Panda 與控制發佈回歸 316 pass、route curve 153 pass、B1/indicator 通過。文件計數 221→222 已調整。既有 official sync gate 的 custom.capnp pin 失敗，移植前後 custom.capnp blob 均為 7aa688efb490715057f1d1b05df51d5d5c30cf9e；保持原門檻不變，獨立處理。新增專用離線 CI 尚待結果。

第二輪：route curve 與 Tesla 設定文件檢查通過；新增完整 controls CI 初次執行 182 pass、15 fail、20 error，所有失敗皆來自隔離測試 Params 缺少 get_int（LateralTorqueCustom），不等於實車測試失敗。測試 harness 僅補上已確認的 LateralTorqueCustom=0、SteerActuatorDelay=0 預設讀取；未知鍵仍報錯、實際 IPC 仍禁止。
另查 custom.capnp：獨立 Test 既有 AmapExitInfo 顯示用欄位未列於舊 pin gate。從現有 blob 僅移除舊五項 PRE 欄位、精確 Amap block 與已知結尾空行後，內容逐字等於舊 pin blob ab580c4a794a4e5e4690490b3dc2cac8d7ccc0db。候選分支 CI 僅加入這兩個精確字串到唯一匹配檢查，保留舊 SHA 與其他安全檢查，不修改 custom.capnp、Panda 或實際車控。需新一輪 CI 確認。
