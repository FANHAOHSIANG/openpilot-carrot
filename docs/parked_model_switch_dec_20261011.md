# DEC 分支整合：C4 停車換模型

整合來源：`FANHAOHSIANG/carrotMAC-HUD` 的
`experimental/parked-model-switch`，固定提交 `30adc3f3f60e17802339efef92083c8fc1e4cce2`。
來源原本只支援官方 `e74e6938ddc4574b1ba19ee7405ff146f3c1728e` 的本機補丁安裝。
本次把其 Jetlink 程式直接整合到 `carrotpilot-dec`，基底 `f06ff13170ec62fd81a2c808ce8b6c8b6f576dac`，
不需也不可在此整合分支再執行原本的 `install_c4_parked.py --install`。

## 啟用

此功能與 CarrotDEC 分開，預設關閉。先安裝此分支，Mac 使用相容的 JetLink 0.8.5／Protocol 3。
關閉車輛電源，保持 C4 供電並等真正 offroad。於 C4 SSH 執行：

```sh
python3 /data/openpilot/openpilot/tools/jetlink/configure_parked_switch.py --enable
sudo reboot
```

整合版設定工具先檢查 offroad、執行 CPU 測試、再次檢查 offroad，才建立啟用檔
`/data/jetlink-parked-model-switch`。不改 IsOffroad／IsOnroad、不備份或覆蓋原始碼。
若狀態在寫入後改變，會還原原有啟用檔狀態。它不驗證實際 QCOM/USB/CAN 行為。

## 換模型流程

車輛 READY、P 檔、未啟用輔助駕駛，且 vEgo/vEgoRaw 絕對值皆小於 0.01 m/s、
standstill 與 CAN 正常。carState/selfdriveState/carControl 必須有效、存活、資料不到 250 ms，
控制 enabled/active/latActive/longActive 均關閉，條件持續至少 2 秒。

啟用後，只要在符合條件的 P 檔就會暫停外接模型，即使不打算換模型。
modeld 先關閉外接 IPC，必要時重置內建 recurrence，至少完成 3 次內建輸出，
持續更新 `parked_switch_ready`。daemon 收到新鮮確認後才釋放舊模型請求，允許 App 選模型。

```sh
cat /dev/shm/carrot-jetlink-model.json
cat /dev/shm/carrot-jetlink.json
```

確認 `parked_switch_ready` 為 true 且 `updated` 持續更新，再在 Mac 點 Use Model。
未知 host、Protocol 2 與 Jetson 不獲得新增停車核准權限。
離開 P 檔、移動、啟用控制、CAN/資料失效或內建輸出停止，核准窗口會撤銷。
下載/編譯工作可能繼續，但 C4 不核准新模型。

P 檔期間保持內建模型；換好後在靜止且未啟用控制時排入 D 檔，才允許外接模型重新接入。
等 C4 確認外接推論運作，再啟用輔助駕駛；不可在行駛或控制已啟用時接入另一個 session。
若窗口沒就緒，回到正常熄火選模型流程，不要靠移動車輛完成核准。

## 停用

真正 offroad 下執行：

```sh
python3 /data/openpilot/openpilot/tools/jetlink/configure_parked_switch.py --disable
sudo reboot
```

只移除啟用檔，不將 DEC 分支的程式覆蓋成舊版本。原本單獨安裝器的 rollback 不適用於本整合。

## 驗證

原補丁的 25 個 CPU 測試在新基底通過。新增 1 個目前 `openpilot.cereal.messaging` 命名空間訂閱測試，
避免舊 `cereal.messaging` 匯入在新版失效；新增 8 個 offroad 設定工具測試。
15 個 DEC 測試及 Python 語法檢查通過。測試替代服務、USB、GPU、契約驗證器與硬體 I/O。
尚未完成 C4／Ioniq 5／TURZX 實機驗證、完整模型測試集或道路閉迴路驗證。

來源為既有停車交接補丁；DEC 計畫、雷達選擇與模型本體保持本分支現況。
已核准模型仍使用既有 spec 驗證與原子核准紀錄，不繞過契約檢查。
