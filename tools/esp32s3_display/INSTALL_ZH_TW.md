# TURZX 9.2 吋 Wi-Fi HUD 安裝

這份測試版由 C4 繪製 HUD，再經 2.4 GHz Wi-Fi 傳給 ESP32-S3。切換 C4 小模型與 Mac mini 的 JetLink 大模型時，HUD 可以固定接在 S3 旁。大模型仍用 C4 Port 2 接 Mac 的 USB 資料線。使用無線接收板時，畫面採用 C4 的 HUD 版面。

## 準備硬體

- ESP32-S3 **N16R8** 開發板，16 MB Flash、8 MB Octal PSRAM，有分開印著 `UART` 和 `USB` 的接孔。
- TURZX **9.2 吋 1920 × 462**，USB 裝置 ID `1CBE:0092`。
- 外接供電的 USB Hub、5V USB 電源及 USB 資料線。

## 刷 ESP32-S3

1. 解壓縮韌體 ZIP。電腦要有 Python 3。從該資料夾開 Terminal 或 PowerShell，執行 `python3 -m http.server 8000 --bind 127.0.0.1`。Windows 若用 `py` 啟動 Python，可改成 `py -m http.server 8000 --bind 127.0.0.1`。
2. 用電腦的 Chrome 或 Edge 開啟 <http://localhost:8000/>。把 ESP32-S3 開發板的 **UART** 孔接到電腦。
3. 新板選 `처음 설치`，原有 CARROT 韌體的板子選 `기존 CARROT S3 업데이트`。勾選板子確認框並按安裝，選開發板的 CP210x／USB Serial 序列埠。等進度完成後拔下。更新模式會比對分割表並保留 Wi-Fi 和配對資料。

也可在解壓縮資料夾內用 `esptool` 安裝新板。把 `PORT` 換成你的 UART 埠，例如 Windows 的 `COM14`。已有 CARROT 韌體時請用上面的更新模式。

```sh
python3 -m pip install esptool==4.13.0
python3 -m esptool --chip esp32s3 --port PORT --baud 460800 write_flash --flash_mode dio --flash_freq 80m --flash_size 16MB 0x0 bootloader.bin 0x8000 partition-table.bin 0x10000 carrot-s3.bin
```

## 接線與配對

1. 在停車時將 C4 更新到 `test/turzx-wifi-hud-20261115`。先讓 C4 連車內的 **2.4 GHz Wi-Fi** 或手機熱點。網路要允許兩台裝置互通。iPhone 開熱點時可開啟「最大化相容性」。
2. 把 S3 的 **UART** 孔暫時接到 C4。從 C4 終端機執行一次配對。`--auto` 需要只有一個符合的序列埠，否則用 `--port` 指定該板的實際埠。若 NetworkManager 沒有授權讀取 Wi-Fi 密碼，可加 `--ssid "你的 Wi-Fi 名稱"` 並在提示時手動輸入密碼。

   ```sh
   cd /data/openpilot
   python3 tools/esp32s3_display/provision.py --auto
   ```

3. 配對後拔掉 C4 與 S3 之間的暫接線。S3 的 **USB** 孔接 Hub 的上游線，TURZX 接 Hub 的資料孔。Hub 另接 5V 電源。S3 的 **UART** 孔可改接 5V USB 電源供板子運作。
4. 在 C4 選「顯示 → 外部 HUD → TURZX 9.2 吋」。停車可用 HUD Debug 的常亮模式測試，完成後調回關閉。畫面出現後，依序確認 Mac 關機仍能顯示、Mac 以 USB 跑 JetLink 時仍能顯示，以及 Wi-Fi 重連後畫面恢復。

如要改回 USB 直連，先把 `/data/carrot/cluster_wifi.json` 移到備份位置，再重啟 C4 並把 TURZX 接回 C4。這個配對檔應留在自己的裝置上。

## 韌體來源

韌體從 CarrotPilot 1.2.1 原始碼重建，採用 ESP-IDF 5.4。舊版曾在開發者的硬體驗證。這份重建版仍需在你的 C4、S3 和 TURZX 實機驗證。

[移除前的原始碼](https://github.com/ajouatom/openpilot/tree/ba186915179816a9b0476cec52bf321e73d2d4b0/tools/esp32s3_display) · [原開發者重連紀錄](https://github.com/ajouatom/openpilot/blob/9af82818a6a3dcdba3cc13d34b04689e0063b6de/docs/s3_reconnect_20261019.md)
