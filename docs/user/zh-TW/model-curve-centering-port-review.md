# 模型彎道置中移植候選（僅離線審查）

基底 fc17546f5c870b7638e42221230d58e22d132ebf；原始實作 cc13575e；參考融合版 5eda71aad247220246bc8b662b6d5642e9c481fb。
只移植 IONIQ 5 的選用模型曲率修正、設定與診斷。預設關閉。保留獨立 Test 的 CarrotPlanner、既有模型 0.1 秒平滑與 clip_curvature；不改縱向控制、車控限制、CAN/Panda 或 HKG 扭力。獨立 Test schema 尚無 plannerProfile，因此不宣稱 Autospeed 相容。
開關、車道線模式、接管、方向燈、變道、導航轉彎、資料新鮮度、標定等拒絕條件沿用融合版。新增 schema 欄位使用融合版相同 ordinal；@68 為保留相容欄位。
本候選未執行完整 native CI、實車或離線真實路線回放；僅可作離線審查，不可部署。
