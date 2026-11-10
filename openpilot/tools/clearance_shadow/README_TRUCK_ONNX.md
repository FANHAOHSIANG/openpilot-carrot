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
