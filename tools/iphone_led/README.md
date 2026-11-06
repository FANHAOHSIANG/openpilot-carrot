# C4 / iPhone / Mac 後窗 LED

2026-11-06 整合至 `carrot-wip`。

## 程式位置與啟動

- `ios/`：CarrotLEDProbe iPhone 原生 App 原始碼（0.14）。Mac 使用 XcodeGen 的 `project.yml` 重新產生含 Live Activity extension 的專案，再簽署並安裝；不能只替換舊專案的 Swift 主檔。C4 與 iPhone 接入同一區網，iPhone 以 BLE 控制 LOY PLAY 屏幕。
- `mac/`：既有 Mac LED / Carrot HUD 測試工具（0.4.1），執行 `START.command`。Mac 與 iPhone 是兩個獨立客戶端；Mac 不包含後續只在 iPhone 加入的全部 UI 功能。
- `openpilot/selfdrive/carrot/iphone_led_bridge.py`：C4 正式橋接入口。manager 僅在 TICI/C4、行車介面已啟動且 `/data/iphone-led/token` 存在時執行，使用獨立 spawn 程序並在崩潰後重啟。
- `c4_carstate_bridge.py` 和 `ios/c4_carstate_bridge.py`：可單獨執行的相同橋接副本，支援 `CARROT_LED_TOKEN` 或上述固定金鑰檔。

橋接僅訂閱 `carState`，不發送 CAN 或控制指令。HTTP 埠為 18765、路徑 `/carstate`，需要 `Authorization: Bearer <金鑰>`。金鑰是 20–128 位 ASCII 英數字；沿用已配對的金鑰即可，不要將它提交到 Git。資料超過 0.7 秒未更新會回報 `valid: false`。

屏幕預設為 96 × 16（1536 顆燈）。iPhone 包含五組自訂文字、車況文字編輯與效果、系統調色盤、獨立字型選擇頁、像素設定、清屏、BLE/C4 自動重連及倒車提示。D 檔煞車／持續動能回收減速優先於單邊方向燈；急減速加雙黃燈觸發「減速中／前方塞車」交替。詳見各客戶端 README。

## 整合來源與導航檢查

基底為 `334a4ac52379f8e4aa0783d6637f34046d2ba892`，LED 來源為 `0f6aab8856a6e3dfede366d507ef81be71e06661`。只帶入 LED 目錄、橋接與 manager 登錄，保留正式版既有變更。

| 功能 | 查核結果 |
| --- | --- |
| 直接輸入座標／停用付費地址搜尋 | 基底已含 `8daba165`；後端地址搜尋仍回傳 410，不復原測試分支的地理編碼功能 |
| Google Maps 分享／配對工具 | 基底已含 `cfdccbe6`、`88f2ffb1` |
| 分享捷徑網址初始化／快取更新 | 基底已含 `1957ae2f` |
| Mac／HUD 導航整合 | 基底已含 `2b7a6adf`；HUD 地圖到期、斷線及傳輸預算測試通過 |
| N16 無損傳輸協商 | 基底已含 `a5dfa247`；Mac protocol-3 傳輸測試通過 |
| Jetlink prepare-only 恢復 | 基底已含 `8b1ea2b7`、`4aaa9b99`；不發布恢復幀的回歸測試通過 |
| 原廠減速帶／學區／區間提示誤擋座標導航 | 本次補正：新增 `CarrotMan.externalNavigationActive @37`，傳送既有外部連線判定；navd 與指令轉送不再以 `activeCarrot` 警示數值推斷來源 |

真正的外部導航仍具有優先權，即使沒有當下轉彎指令；外部來源失效或斷開時重新計算已儲存座標路線。GPS 有效性和既有減速計算不變。schema、發布者及 navd 必須一起更新並正常重新啟動 C4 程序。沒有整批合併測試分支中的官方更新、其他車型或控制實驗。

## 驗證範圍

- Python：184 項通過，另 2 個 subtests；LED 協定／畫面／HUD 連動、橋接認證及資料過期、座標 API、Google 分享配對、navd 來源切換、車況來源發布、Jetlink prepare-only、HUD 導航圖及 Mac N16 傳輸。
- Node：10 項通過；分享確認、座標直接送出、無效輸入、取消確認及地圖狀態。
- 89 項 Python 測試直接在桌面環境執行；另 95 項使用真實 Cap'n Proto schema 與實作，隔離原生 IPC、硬體與 Params，並略過不相關的網頁模組初始化。不是 C4 原生建置或實車測試。
- 此環境沒有 Xcode；本次未編譯或安裝 iPhone App。BLE 動畫仍是手機逐格傳送，尚未驗證為屏幕原生跑馬燈；iOS 可能暫停背景網路與動畫。

GitHub 更新不代表 C4、iPhone 或 Mac 已更新。C4 停車後以正常分支更新／重啟流程安裝；iPhone 另以 Xcode 安裝，Mac 另使用本目錄的工具。
