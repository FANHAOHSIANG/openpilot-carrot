# 高德一般版 / 車機版高精定位雙線研究
2026-11-28，唯讀診斷及離線回放；不改車控或既有導航來源選擇。

## 共同資料目標
區分 GNSS 絕對座標、道路匹配、物理車道索引、車道相對橫向偏移、路口推薦圖示、原生路線幾何。禁止從其中任一項推定其他項。
來源記錄應保留 session、route ID/epoch（缺失則 unknown）、原始事件類型、來源單調時間或接收時間、座標系、索引基準、單位及可信度；缺失不填零。不得在未驗證時使用來源自報 accuracy 代替實際定位誤差。

## 一般版（L1/L2/L4 候選）
固定既有證據：[APK 靜態驗證](https://github.com/FANHAOHSIANG/Carrot-Bridge/blob/ad64e7cdb24d1a2908db720a1f7972a24d44ab0f/variants/gaode-lane-probe/AMAP-17.05-VALIDATION.md)；[wide.86 採集](https://github.com/FANHAOHSIANG/Carrot-Bridge/blob/9ba58d01786848708ab887674741fb131e1517e2/variants/wide86/README.md)。
1. 正常授權 Link，先離線查 Type 4 / 16 原始事件，與 Type 14 車道引導、Type 2 路線對照；按導航有效/取消/切換分段，統計非空欄位及變化率。
2. 靜態候選 LaneMatchInfo.laneMatchData、accuracy、tickTime、updateUtcTime，以及 LocPlaneMatchInfo.laneIdx、lateralDis、longitDis2Start、state。尚未取得有效樣本，不能猜二進位格式、單位、座標系、索引起點。AmapLocationSubService 非 exported；不繞過權限、不修改原廠 APK。
3. 官方 SDK 公開 onLocationChange / showLaneInfo，參考 https://developer.amap.com/api/android-navi-sdk/guide/location-info/location-setting-callback 和 https://developer.amap.com/api/android-navi-sdk/summary/ 。高精物理車道定位與台灣覆蓋、授權需向官方確認；獨立 SDK 的導航不等於原 App 正在導航的同一路線。

## 車機版（並行）
固定 [wide.87](https://github.com/FANHAOHSIANG/Carrot-Bridge/blob/99a832e99fc6d48e2a8f4ff6b44a423296886543/variants/wide87/README.md) / [wide.88](https://github.com/FANHAOHSIANG/Carrot-Bridge/blob/ba2a73816ffafab0ac374d0b25ba842c39a72d95/variants/wide88/README.md)。
利用既有被動採集的 10001/12205/13011/13012 候選，保留原碼；分離定位、推薦車道、路線事件；正常授權互聯有資料才記錄。未證實取得原生定位或完整幾何。不能以一般版的事件碼解釋車機版。

## 騰訊 tc-v61 參考（方法而非高德介面）
L1 事件生命週期、L2 前方車道、L4 高頻匹配相互分離；車道 ID/原始索引/比例/坡度/置信度分欄。騰訊文件中 egoBase unknown，L4 約 10Hz 不是高德頻率保證。不移植第三方私有程式或注入方案。既有 js/lane-evidence.js 僅是正規化契約，尚未接入即時來源。
## C4 獨立相對定位
沿用 gaode_vision_export.py、gaode_lane_shadow.py 及 lane-observe.js 的可信車道線/寬度/局部中心候選，與 GNSS、車身姿態及單調時間進行離線觀察；視覺局部定位不能證明地圖絕對車道 ID。無可驗證對齊時只顯示局部候選。GPS/RTK 絕對精度另需已知參考基準及實地量測；不從 GNSS accuracy 宣稱厘米級定位。
## 驗收
優先重放既有私有 Bridge ZIP、C4 JSONL/rlog，不把定位原始資料上傳 GitHub。若缺有效樣本，停車設定採集，由乘客記錄正常導航；比較明確道路與車道數變化、路線切換/撤銷、時鐘與座標系、缺失/過期；不為測試而做額外變道，不啟用控制。真實樣本未驗證前推薦及絕對索引維持 unknown。Mac AR 投影另驗證校正與時延。
