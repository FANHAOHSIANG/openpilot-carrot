# Carrot 車道觀察 v1
使用 wide.87 搭配既有 C4 Web，停車更新到包含此提交的 Test 分支。連接 C4 網路，在手機／平板瀏覽器開啟 `http://<C4-IP>:7000/lane-observe.html`。停車按開始連線、開始紀錄，乘客觀察或將頁面留在前景。停車後停止紀錄並匯出 JSONL，連同 Bridge 診斷 ZIP 與同路段完整 rlog 提供分析。頁面關閉、隱藏不會持續採集，匯出前不要重新整理。沒有改 APK，不需 Mac，不接管既有導航投屏，沒有常駐程序、模型或控制訊息。僅在頁面開啟時使用現有 raw multiplex relay，有額外網頁連線／解碼成本，未量測實機負載。
 
導航車道依 C4 carrotNavi laneCurrent.meta.present、visible、接收時間及 count 驗證。available 為原始值，非自車車道或安全變道指示。視覺與導航的時間差為 C4 內部時鐘，手機精確對時／座標系統、絕對車道序號及分流拓撲仍未驗證。沒有把導航車道與模型幾何直接畫成同一路徑。所有輸出 control_usable=false。5 Hz 記錄／9000 筆上限；不含完整路線或 GPS，不上傳任何資料；仍可能含時間與車況，請自行保管。車道線／道路邊界為模型估計，不能取代駕駛觀察。低速轉向角及控制曲率提供額外觀察，並非低速抖動修復。
 
現有 raw_capnp.js 僅增加 Navi ItemMeta 原始欄位與可選 keepNaviMeta 參數；預設既有輸出保持不變。既有控制、planner、loggerd、cereal schema、web server、HUD 資料源不修改。
