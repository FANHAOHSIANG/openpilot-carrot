iPhone / C4 / LOY LED 區網連動原型 0.5

架構：C4 只讀車況橋接 → 區網 → iPhone → 藍牙 → 96 × 16 LED。
這是 Xcode 原始碼，需用 Mac 的 Xcode 簽署並安裝到 iPhone。

本版：
- 車況觸發左右轉彎文字與移動箭頭，其他車況文字和優先順序沿用原版。
- 五組自訂文字可選顏色、字重與靜態、閃爍、左右跑馬燈、呼吸、自動換色、左右動態箭頭、波浪、愛心及警示圖案。圖案以參考影片為靈感，非逐格複製。
- 使用者輸入的半形空格會以不換行空格渲染，保留字間距，不修改原本儲存的字詞。
- 藍牙、C4 嘗試自動連接；金鑰保存在 iPhone 鑰匙圈。C4 固定金鑰和自動啟動仍需另行安裝測試分支。
- 車況優先於自訂文字；資料失效時嘗試清屏。

注意：此環境無 Xcode，Swift 新版尚未編譯與實機測試。請先停車測試文字空格、箭頭方向、效果、切換延遲、殘影及斷線清屏。完整畫面逐格更新能否避免閃爍或殘影，取決於 LED 實際行為。iOS 可能暫停背景網路與動畫，不能保證背景更新或清屏。BLE 回覆尚未確認，斷線時畫面可能保留。

C4 的固定金鑰自動啟動方案在 GitHub 獨立測試分支，尚未安裝到 C4；HTTP 僅限可信私人網路，金鑰和車況不加密。既有臨時橋接仍可用；金鑰每次啟動會改變。

安裝更新：在 Mac 解壓，結束 Xcode，把 CarrotLEDProbe.swift 和 Info.plist 取代到原 Xcode 專案目錄，重新開啟專案並用 Xcode 對 iPhone 執行。只更動 iPhone 程式，不需變更 C4。請勿直接將 GitHub 測試分支併入正在行車的 C4。

0.5.1：僅當實際安裝 App 的 Info.plist 宣告 bluetooth-central 時才啟用藍牙狀態恢復。若 Xcode 使用其他 Info.plist，改為前景連線以避免啟動時例外；要使用背景藍牙，請檢查 Target → Signing & Capabilities → Background Modes 勾選 Uses Bluetooth LE accessories。
