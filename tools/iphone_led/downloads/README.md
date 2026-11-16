# Carrot LED 最新下載：2026-11-09

| 平台 | 下載 | 更新方式 |
| --- | --- | --- |
| Android | [CarrotLED-0.1.10.apk](CarrotLED-0.1.10.apk) | 已裝 0.1.9 可直接覆蓋，設定保留；舊 0.1.8 簽章不同，需先保存設定再移除安裝 |
| iPhone | [CarrotLED-iOS-0.31-Source.zip](CarrotLED-iOS-0.31-Source.zip) | Mac 解壓後 xcodegen generate，沿用原 Personal Team／兩個 Target Bundle ID，用 Xcode 安裝 |

[背景模式、通知與區網診斷](../BACKGROUND_UPDATE.md)

Android 首先允許附近裝置與通知，啟用背景車況通知，按「3 秒後測試通知」再切到導航。若通知列可見、橫幅不可見，檢查車機的浮動通知設定、勿擾及通知冷卻。通知表示 App 收到車況，不是屏幕回讀。

iPhone 行車定位會顯示手機 GPS 速度與本次里程；請允許使用 App 期間定位。開始後等 GPS 與 C4 都更新再切換 App；停止即停止定位，不保存／上傳軌跡。只靠動態島或背景處理任務無法保證常駐。實機背景與實體 LED 效果仍待確認。

## C4 IP 與金鑰

在 C4 SSH 執行：
```sh
ip -4 -o addr show wlan0
cat /data/iphone-led/token
```

把 IP 去掉 `/24` 等子網尾碼，與金鑰填入 App。原本 C4 金鑰不需要重建，不要公開分享。

## 簽章與檢查

Android 0.1.10：versionCode 11，套件 tw.carrot.led；沿用 0.1.9 簽章 SHA256 `1cf22fc66c9b3333d93077bb40102135186732570614d754e45536e4fd2b799d`。私鑰保留在私人備份，不在 Git。

iPhone ZIP 是 Xcode 原始碼專案，不是 IPA 或 TestFlight。安裝時重新產生專案，不能只換 Swift 主檔。
