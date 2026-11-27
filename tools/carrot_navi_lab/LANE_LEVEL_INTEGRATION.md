# 車道級導航研發整合清單（2026-11-28）
獨立分支 test/c4-vision-ar-hud；基底 b5eaadeacfcbaf2f3a403e179cd7093236a9bad9。不修改原 Test / Tony、車控或導航發布。
## 保留既有成果（不重寫）
- C4 Web: lane-observe.html、js/lane-observe.js、js/lane-hud-observe.js、raw_capnp.js、原有 Node 測試。觀察頁 5 Hz / 9000 筆 JSONL、off/auto/always、原始 lane flags、雙線中心/路邊界/模型軌跡。主 HUD 設定仍預設 off，使用同一額外 WebSocket，現增加 modelV2 與導航事件並列；模型超過 600ms 不顯示、導航失效清除，C4 訊息時間差 <=250ms 僅表示時間接近，不是空間匹配。
- C4 離線工具: tools/carrot_navi_lab/gaode_lane_shadow.py、gaode_vision_export.py 及各自測試；原生中心線比較要求 C4 局部座標、單調時鐘、已驗證對齊；保留 LANE_OBSERVE.md / LANE_OBSERVE_V2.md。
- 騰訊 tc-v61 技術文件：參考 L1 事件、L2 車道預覽、L4 高精定位、routeEpoch、session/seq、單調時鐘、不可變快照；已建立 lane-evidence.js 獨立正規化契約及回歸測試。不是騰訊真實 wire schema；未接入授權資料來源；egoIndex 基準未知。不得把引導圖示數視為物理車道數。
## 跨儲存庫既有成果（固定來源，不複製 APK 或私有資料）
- Carrot-Bridge [GaodeProbe](https://github.com/FANHAOHSIANG/Carrot-Bridge/tree/ad64e7cdb24d1a2908db720a1f7972a24d44ab0f/variants/gaode-lane-probe)：高德一般版 17.05 靜態驗證、正常授權 Link；類別存在不等於可讀或有台灣資料。
- [wide.87](https://github.com/FANHAOHSIANG/Carrot-Bridge/tree/99a832e99fc6d48e2a8f4ff6b44a423296886543/variants/wide87)：車機版被動廣播，保留 86 一般版；原生幾何未證實。
- [wide.88](https://github.com/FANHAOHSIANG/Carrot-Bridge/tree/ba2a73816ffafab0ac374d0b25ba842c39a72d95/variants/wide88)：高頻與低頻事件分開配額、巢狀 Bundle、有界採集。此次不修改 Bridge，不宣稱 APK 已簽署發布。
- 11/27 既有 C4 文件記錄 count=3/4，available 空白。既往對話報告 KEY_TYPE=13012/EXTRA_DRIVE_WAY；需原始 ZIP/JSONL/rlog 再現才能驗證推薦方向及數量統計。禁止從 count 或轉向猜測推薦。
## 測試
停車使用 C4 Web /lane-observe.html，開始連線、紀錄；主 HUD 開關選 auto，返回主 HUD；有有效事件時並列導航車道數與 C4 可見局部候選；無有效事件隱藏。停車匯出 JSONL，連同 Bridge 診斷及同時段完整 rlog。乘客操作。未驗證 C4 原生直連顯示器、Mac Jetlink 3D 投影、原生路線座標、實機負載或空間匹配。無轉向/變道/巡航寫入。
