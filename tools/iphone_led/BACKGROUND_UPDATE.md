# 2026-11-09：iPhone 0.31、Android 0.1.10 與區網檢查

## iPhone：加入真正的行車定位模式

0.30 的 BGContinuedProcessingTask 不是無限背景執行保證，Apple 可收回任務。0.31 預設提供「行車定位模式：GPS 速度與本次里程」，開始行車後使用 Core Location 背景定位，動態島同時顯示手機 GPS 速度與估算里程。位置只留在記憶體，不存軌跡、不上傳；GPS 絕不替代 C4 的煞車／方向燈／車況。定位有耗電及系統定位指示。

開始前連接 C4 與 LED、開屏並開啟自動車況。按開始背景連動，允許「使用 App 期間」定位，等手機 GPS 與 C4 都更新後才切出。停止連動、關屏、清屏或手動斷開 C4 會停止定位。完全無橋接回覆 5 分鐘亦會停止；車況 0.9 秒過期清屏規則不變。不要從多工畫面強制滑掉 App。

此模式不會建立舊的處理任務進度橫幅，但正常動態島與系統定位指示仍會顯示。關閉行車定位模式才回到實驗性處理任務。系統仍可能中止、定位不可用或網路切換仍可能斷線；編譯／模擬器通過不代表真機背景已證實成功。

若不願使用背景定位，另一路是由伺服器透過 APNs 更新 Live Activity。這需要 Push Notifications 的開發者資格與後端設定，而且只更新動態島，不能保證手機背景持續控制 BLE LED；本次沒有假稱已建好 APNs。

## Android：通知與區網修正

- 收到車況通知不再要求 LED 已開屏／連線。
- 短暫訊號結束不會立即撤掉已送出的「收到車況」提醒；最多保留設定的 6 秒，失聯／暫停時撤掉。
- 多視窗時以焦點判斷背景，避免 Activity 仍 resumed 就一直不通知。
- 新增「3 秒後測試通知」，不需 C4 或 LED。通知權限與頻道關閉會明確顯示；拒絕通知不再阻止前景服務連線。
- 依目的 C4 IP 的最長相符區網路由選網路，包含乙太網路，不再固定選第一個 Wi-Fi。不會切換全機 Wi-Fi、開 VPN 或綁定其他 App 的網路。
- 顯示 HTTP／例外類型、延遲、請求／橋接回覆／有效車況／失敗數，並可複製不含金鑰的診斷。0.1.10 沿用已備份的 0.1.9 簽章，可直接覆蓋 0.1.9；0.1.8 才需要先保存設定、移除後安裝。

## CP 搭子寬螢幕與 C4

檢查使用者的 wide.2 修改套件：修改範圍為布局、投屏啟動／本機計時，未見修改 LED 的 18765 埠。官方 README 列出 CP 搭子 7000 Web、7705 發現、7706 資料；LED 使用 TCP 18765。沒有直接同埠衝突的證據，但這不排除投屏壅塞、Wi-Fi 切換、車機省電或 C4 負載。沒有取得這次實機網路紀錄，因此不能認定 C4 或 CP 搭子無問題。不要同時運行官方 CP 搭子與寬版的轉送服務。

C4 唯讀橋接改為 HTTP/1.1 可重用連線，閒置連線逾時 2 秒，避免每筆輪詢都重建 TCP。已測三個客戶端各 20 次重用連線；金鑰保護與 0.7 秒 C4 原始車況過期規則保持不變。需要更新 C4 的 iphone_led_bridge.py 才會啟用此改善；新版手機仍相容舊橋接。C4 請停車後以原方式更新測試分支並重啟，不要行車中更新。

## 怎麼分辨問題

1. Android 先按「3 秒後測試通知」，立即切到 CP 搭子。如果通知列有但沒有橫幅，檢查車機的浮動通知／勿擾／Android 通知冷卻；如果通知列也無，先查 App 與頻道權限。這項測試不受 C4 是否有車況影響。
2. 只開 LED 30 秒，複製診斷；再開 CP 搭子及投屏 30 秒，再複製一次。比較有效車況、失敗與延遲。測試時只讓一支手機／車機控制同一塊 BLE 屏幕。
3. C4 上可做不輸出金鑰的本機讀取測試：

```sh
cd /data/openpilot
python3 tools/iphone_led/diagnose_link.py --seconds 30
```

本機也沒有 HTTP 回覆：先查橋接程序。HTTP 正常但沒有有效 carState：先查 C4 車況來源。C4 本機正常但車機逾時：再查區網路由／無線品質／投屏負載。Android 與 iPhone 仍需實機測試，這些判讀是排查方向，不是已確認根因。

來源：
- https://developer.apple.com/documentation/corelocation/cllocationmanager/allowsbackgroundlocationupdates
- https://developer.apple.com/documentation/backgroundtasks/bgcontinuedprocessingtask
- https://developer.android.com/develop/ui/compose/notifications
- https://github.com/jixiexiaoge/openpilot
