# C4 ONNX Vision 大車辨識測試版

此分支沿用官方 ONNX Vision 的廣角取像及左右多邊形，使用分支內附的 truck-best.onnx。
在 Carrot Web 開啟「ONNX 車道與盲點識別」以啟動 ShareData 服務。視覺 BSD 可獨立切換。

停車熄火時執行：

```bash
cd /data/openpilot
export PYTHONPATH="$PWD/pydeps:$PWD${PYTHONPATH:+:$PYTHONPATH}"
python3 -m openpilot.tools.clearance_shadow.live_observer arm --with-jetlink
```

不連接 Mac 時可使用一般 arm。status 顯示辨識狀態，off 可提前結束。
狀態也在 ONNX Vision 的原始狀態 JSON 中，以 truckShadow 欄位提供。

限時五分鐘。每兩秒最多取一張廣角影格，依負載延長等待。
辨識結果與候選遠離方向只供觀察。方向由辨識框落點和區域判定，
同時有兩側目標、來源不明或框被影像邊緣裁切時不產生候選方向。
候選方向沒有接到轉向、煞車、規劃器或 BSD。廣角準確度與實機負載待驗證。

## 偏移評估開關與紀錄

`offset-on` 與 `offset-off` 可開關偏移評估，預設關閉。先用 `arm` 啟用辨識。
每筆 truckShadowObservation 會記錄 requested_offset_m、applied_offset_m 與 cancel_reason。
請求是影像候選方向的試算值（向左為負，向右為正，幅度 0.15 m），沒有經過車道空間驗證。
實際套用值固定為 0。車道可用空間與目標追蹤通過回放驗證前，這版僅供觀察。

## Carrot Web 開關

在 ONNX Vision 詳細頁使用「大車辨識」。開關可隨時操作，設定保存到 OnnxTruckEnabled，C4 重啟後也會保留。
開啟時自動啟用 ONNX Vision 主服務。車輛啟動且有可用影像時持續辨識，停車或主模型狀態不佳時暫停推論。
關閉開關即可停止，無需重新輸入 SSH 指令。
舊的 SSH arm 指令仍是五分鐘模式。要從終端機啟用持續模式，在 arm 後加上 --continuous。
持續模式沿用單一背景工作、至少兩秒取樣間隔與 CPU 用量冷卻時間。

