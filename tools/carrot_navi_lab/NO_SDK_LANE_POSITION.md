# 無 SDK 車道級定位：第一階段診斷
沿用既有 C4 Web 觀察頁，沒有新模型、Android SDK、控車或導航寫入。relative_position 是 schema 3 JSONL 新欄位，保留原 schema 2 欄位內容。用模型座標 x=0 的左右內線估算原點相對車道中心（+右、-左）；以 x=2、5 檢查近端幾何、可信度、寬度及道路邊界。缺少 x=0 直接撤回，不由 10m 中心外推。不確定模型原點對實車參考點的校正，禁止當成車身淨距、絕對車道或精度證明。
停車開啟 http://<C4-IP>:7000/lane-observe.html，開始連線、開始紀錄。先看有無局部候選；乘客觀察正常行駛，停車停止並匯出 JSONL。用同路段 C4 rlog / Bridge ZIP 驗證資料新鮮度及實際車道語意。不必為測試進行額外變道。未驗證前僅診斷頁，不添加主 HUD 駕駛引導。
一般版正常授權 Link Type 2/4/14/16、車機版 13012 等仍並行；既有 wide.86/87/88 採集不改。參見 HD_POSITION_RESEARCH.md 和 LANE_LEVEL_INTEGRATION.md。下一步：回放已取得記錄、校正模型座標參考點、對齊 GNSS/IMU 與導航資料，確認真實來源後才驗證 AR 投影。
