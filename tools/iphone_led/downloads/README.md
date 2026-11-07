# Carrot LED 下載與安裝

更新日期：2026-11-07。這裡提供 Android 安裝 APK 與 iPhone Xcode 專案包。

| 平台 | 下載檔案 | 如何安裝 |
| --- | --- | --- |
| Android 手機／車機 | [CarrotLED-0.1.2.apk](https://github.com/FANHAOHSIANG/openpilot-carrot/raw/refs/heads/carrot-wip/tools/iphone_led/downloads/CarrotLED-0.1.2.apk) | 在 Android 裝置下載，開啟 APK 安裝 |
| iPhone | [CarrotLED-iOS-0.19-Source.zip](https://github.com/FANHAOHSIANG/openpilot-carrot/raw/refs/heads/carrot-wip/tools/iphone_led/downloads/CarrotLED-iOS-0.19-Source.zip) | 在 Mac 解壓，用 Xcode 簽署並安裝到 iPhone |

**iPhone 的 ZIP 是原始碼專案，不是 IPA，也不是 TestFlight 安裝連結。請在 Mac 下載。** 若進入 GitHub 檔案頁，按右上角「Download raw file」下載。不要下載整個 openpilot 倉庫來安裝手機 App。

## 安裝前

- C4 需已有可用的 LED 車況橋接。已成功連動的 C4 沿用原設定，這次下載與安裝手機 App 不需重裝 C4。尚未設定者先看[橋接說明](../README.md)。
- C4 與使用中的手機／車機接入同一個可互通的區域網路；不要使用隔離裝置的訪客網路。
- 同一塊 LED 先只交給一個客戶端連接；請先讓 LOY PLAY、Mac 或另一支手機斷開。
- 這款屏幕設定為**寬 96、高 16**，不是車機螢幕的 1920 × 720。請停車完成設定與測試。

## Android 車機安裝（包含 Android 15）

1. 在車機瀏覽器下載上方 APK；也可以先在電腦下載，再用 USB 隨身碟傳到車機。
2. 用車機「檔案管理」開啟 `CarrotLED-0.1.2.apk`。若系統阻擋，依提示允許該瀏覽器或檔案管理器「安裝未知應用程式／允許此來源」，返回後安裝。
3. 開啟 **Carrot LED**，允許「附近裝置／藍牙」與通知權限。Android 11 以下另需掃描所需的位置權限與位置開關。
4. 進入「連線」頁，輸入 **C4 目前的區網 IP** 與 **橋接金鑰**，按「儲存連線設定」。已儲存金鑰時欄位可留空；IP 欄只填位址，不加 `http://` 或連接埠。
5. 按「開始背景連動」，到「屏幕」頁掃描／選擇 LED；曾選過的屏幕會嘗試重連。確認狀態區的 C4 車況與藍牙都連通，再打開「自動車況」。
6. 在「快捷」頁按任一車況或自訂文字旁的「顯示」，確認實體 LED 有反應。車況預覽約 5 秒後恢復原模式。
7. DUDU 車機可在背景／電池管理允許 Carrot LED 執行，選項名稱依韌體而異。確認常駐通知出現後再切到導航，並確認 LED 仍有更新。

寬螢幕會自動採左右雙欄，窄視窗採上下布局；狀態與清屏控制維持可操作。最低 Android 8.0。車機需讓第三方 App 存取 BLE，能連手機通話不等於能連 BLE 屏幕。

**更新舊版：**直接安裝 APK 覆蓋，不要先刪 App。這個 APK 與先前交付版本沿用同一測試簽章；如果遇到簽章衝突，先保留舊 App 與設定並確認原安裝來源，不要直接刪除重裝。

此版背景服務需由 App 按「開始背景連動」啟動，每次最多 8 小時；不是開機自啟。車機休眠、斷電或系統強制停止後，請回 App 檢查並重新開始。

## iPhone 安裝（Mac + Xcode）

### 1. 準備 Mac 與 iPhone

1. Mac 安裝可支援目前 iPhone 系統的 Xcode，首次開啟完成必要元件安裝。
2. 在 Xcode → Settings → Apple Accounts（部分版本稱 Accounts）登入自己的 Apple 帳號。
3. 用 USB 接上 iPhone，解鎖並按「信任這部電腦」。若提示開發者模式，至 iPhone「設定 → 隱私權與安全性 → 開發者模式」開啟，依提示重新啟動並確認。若找不到選項，先完成 Xcode 的裝置配對流程。

App 最低 iOS 16.2；本版的背景行車連動啟動功能限定 iOS 26 以上，動態島顯示也需要支援動態島的 iPhone。

### 2. 解壓並產生專案

在 Mac 下載 ZIP、雙擊解壓，開啟裡面的 `iphone_led_lan` 資料夾。應看到 `project.yml`、`LiveActivity`、`Resources` 等檔案與資料夾。

開啟「終端機」，輸入 `cd `（後面有一個空格），將 **iphone_led_lan 資料夾**拖進終端機，再按 Enter。接著執行：

```bash
xcodegen generate
open CarrotLEDProbe.xcodeproj
```

如果第一行顯示 `command not found: xcodegen`，已安裝 Homebrew 的 Mac 先執行 `brew install xcodegen`，再重做上面兩行。沒有 Homebrew 時請先依 [Homebrew 官方說明](https://brew.sh/)安裝，或依 [XcodeGen 官方安裝說明](https://github.com/yonaskolb/XcodeGen#installing)選擇安裝方式。

**必須重新產生整個專案，不能只把 Swift 主檔換進舊專案。** 本版需要 Live Activity extension 與靜音提示資源。

### 3. 設定兩個 Target

1. 在 Xcode 按 `Command + 1` 顯示左側檔案列表，點最上方藍色的 **CarrotLEDProbe 專案圖示**。
2. 中央專案設定的 **TARGETS** 清單有 `CarrotLEDProbe` 和 `CarrotLEDLiveActivity`；不是左側一般 Swift 檔案。
3. 先選 `CarrotLEDProbe` → **Signing & Capabilities**，勾選 **Automatically manage signing**，在 **Team** 選自己的開發團隊。
4. 再選 `CarrotLEDLiveActivity`，同樣勾選自動簽署，選**同一個 Team**。
5. Bundle Identifier：若是更新，主 App 沿用手機舊版的完整值，extension 沿用相同前綴再加 `.liveactivity`。若是首次安裝，將預設 `tw.example.carrotledprobe` 改成自己可用的唯一識別碼，extension 也一起改成對應的 `<主 App 識別碼>.liveactivity`。

更新時保留原 Team、Bundle Identifier 和已安裝的 App，可沿用設定及鑰匙圈資料；不要先刪除舊 App。不要把 Apple 帳號、簽署私鑰或 C4 金鑰上傳到 GitHub。

### 4. 安裝與首次連線

1. Xcode 上方 Scheme 選 **CarrotLEDProbe**，旁邊執行裝置選**自己的實體 iPhone**。
2. 按左上角 ▶ 或 `Command + R`，等待編譯、安裝、開啟完成。App 會出現在 iPhone 主畫面／App 資料庫；不是安裝到「檔案」App。
3. 允許 App 的藍牙與區域網路權限。在 App 的設定頁填入 C4 IP 與原本橋接金鑰，按「連接 C4」，再按「掃描並連接屏幕」。
4. 確認收到 C4 車況及屏幕連線；用「顯示」預覽測試。開啟自動車況與「自動啟動背景連動」，等狀態顯示已開始後，再切到其他 App。
5. 要使用換字提示可開啟「換字時展開動態島」。實際展開、收合及更新呈現由 iOS 管理；App 的「最近完成提交」時間不是實體屏幕或動態島已顯示的確認。

若 Xcode 提示 Developer Mode disabled，回到上述開發者模式步驟；若出現開發者磁碟映像無法掛載，先處理 Xcode 裝置準備／系統版本支援，再重新 Run，不需要更動 C4 金鑰。若要求存取 Mac「登入」鑰匙圈，通常是 Mac 的登入鑰匙圈密碼，不是 C4 橋接金鑰。

## C4 金鑰與 IP 在哪裡

兩版都填入 **同一份既有 C4 橋接金鑰**，不是 Apple、Google、Wi-Fi 或 Mac 登入密碼。

已用 SSH 登入自己的 C4 後，可在 C4 終端機唯讀查看：

```bash
cat /data/iphone-led/token
ip -4 -o addr show wlan0
```

第一行輸出的完整英數字串填入金鑰欄；第二行取 `inet` 後的 IP，去掉 `/24` 等網段後綴。IP 可能隨熱點或路由器更換而變動，不要一直沿用舊位址。金鑰請自行保管，不要貼公開截圖或留言。

若金鑰檔不存在，代表尚未完成固定金鑰設定，請回[橋接說明](../README.md)確認；不要猜一組帳號密碼填入。橋接預設使用私人區網 HTTP 埠 `18765`，App 會自動加入連接埠。

## 清屏、預覽與常見狀況

| 狀況 | 處理方式 |
| --- | --- |
| 清屏後不再跟隨車況 | 「清屏」會暫停車況、自訂及預覽；重新開啟「自動車況／自動顯示車況」恢復 |
| 藍牙顯示已連線，但 LED 不亮 | 先按開啟屏幕，再按顯示預覽；確認像素為 96 × 16，其他客戶端已斷開 |
| C4 資料中斷 | 確認目前 C4 IP、同一區網、橋接已啟動與車況持續更新；這與藍牙連線是兩件事 |
| 自訂文字被車況取代 | 自動車況開啟時，車況提示優先，結束後才回到選用的自訂文字 |
| 切背景後停止 | Android 檢查服務通知與車機省電設定；iPhone 檢查行車即時動態已啟動，回 App 重新確認資料；強制關閉 App 不等於一般切背景 |

車況七項為 R檔、左方向燈、右方向燈、煞車、雙黃燈、感謝燈、急煞雙黃燈。每項及五組自訂文字均可獨立儲存文字樣式。iPhone 與 Android 的系統字型不同，效果不一定完全相同；動畫仍為藍牙逐格輸出，未確認等同屏幕原生跑馬燈。

## 本次檔案與驗證範圍

- Android：0.1.2，versionCode 3，套件 `tw.carrot.led`。提供既有已建置並簽署的 APK，本次沒有重新建置或改動功能。
- iPhone：0.19，主 App 與 extension build 19。ZIP 內 13 個檔案逐一比對 GitHub 提交 `bdcdf68c111e8ff3a0cfb9f0c275e39d2eb78529`，內容一致；本次沒有完成 Xcode 編譯或 iPhone 實機驗證。
- 兩份下載檔均通過 ZIP 完整性檢查。[SHA256SUMS](SHA256SUMS)供核對下載檔案。檔案上傳 GitHub 不代表裝置已自動更新。
- 既有版背景連動曾有使用者成功回報；不同車機、iPhone 系統及新版動態島修正仍需實機確認。連線標示與 App 最近送出內容都不是 LED 硬體顯示回讀。

安裝步驟參考：[Apple 實機執行](https://developer.apple.com/documentation/xcode/running-your-app-on-simulated-or-physical-devices)、[Apple 開發者模式](https://developer.apple.com/documentation/xcode/enabling-developer-mode-on-a-device)、[XcodeGen](https://github.com/yonaskolb/XcodeGen)。
