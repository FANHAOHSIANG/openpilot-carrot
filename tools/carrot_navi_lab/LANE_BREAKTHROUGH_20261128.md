# 2026-11-28 車道級突破：四份既有實車 Bridge ZIP 離線盤點
本次在本機讀取四份使用者先前提供的 ZIP 全部 events*.jsonl，僅保存聚合統計，不提交原始位置、路線 ID、ZIP 或身份資料。筆數是紀錄數，未跨檔去重，不代表獨立事件或道路數。
- 車機版兩份：23,805 筆 amap_auto_packet；37 筆 KEY_TYPE=13012，26 筆 enabled=true、11 筆 false。95 筆車道項目中 5 筆 trafficLaneAdvised=true，分布於 3 筆事件；全部 26 筆可見事件圖示序號完整 0..n-1。其他 false 不等於已取得完整推薦，圖示序號不等於物理車道序號。
- 一般版兩份：11,888 筆 amap_link_packet；34 筆 type14 均有等長 laneCount/backLane/frontLane；22 筆 frontLane 同時含 255 與非 255。第三方 HyperCar 對照指出 255 不推薦；仍需原導航畫面校驗。
- type4 3,435 筆 laneMatchResult 全部 laneCnt=0、laneNum=0，不能推斷自車第 0 車道；type16 3,292 筆，3,278 筆 isMatchNaviPath=true（只表示道路路線匹配，自報狀態不證明精度）。
- type2 26 筆 highlightRoute 均能在 info 取出所選路線，全部選中路線 linkInfo 的 lat/lon 陣列成對且數值在經緯度範圍，原始點數 19..341（含重複端點），2,199 次相鄰 link 接合在本次近似距離檢查為零。尚未確認座標系、路線總長與實際終點完整性、即時 route ID / 來源代次及 AR 投影。現有 Bridge wide56 WideAmapLinkRoute.java 已實作選中路線、長度檢查、保留轉向端點；優先沿用，不另造路線。
- 車機版原生 route geometry 未突破。
- wide88 對字串型 trafficLaneAdvised=true 有可能遮蔽：需針對欄位做值型別限縮測試；本次實際找到的 true 為 Boolean，非此問題所致。
## 新增唯讀候選解析器
js/lane-candidate.js，接受已授權取得的 13012 EXTRA_DRIVE_WAY 或 Link 14 data，嚴格驗證數量、序號、代碼、撤回，區分 false 與 unknown。無路線或時間狀態管理、未接入 live HUD；不得把候選直接當成導航控制、車道對位或原生 AR。配合既有 lane-evidence.js 的 route scope/TTL 及 lane-observe.js 相對定位，待畫面回放驗證後才能接入唯讀 HUD。測試只用人工合成資料。
參考互通欄位（未複製程式）：https://github.com/sumgor/AMap-/blob/main/app/src/main/java/com/navi/link/view/LaneLineView.java 及 https://github.com/fw867/hypercar/blob/main/docs/NAVIGATION.md 。
