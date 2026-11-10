# HCOP 道路偏移與 YOLO 大車辨識：離線觀察版

原研究版本基底：`FANHAOHSIANG/openpilot-carrot` 的 `test/carrot-wip-upstream-20261104`，
`97830a1ffe5b079c1326da0b97ed065cbb4ea125`。

這版可執行「錄影辨識 → 追蹤 → 車道幾何比較 → 偏移試算 → JSONL/影片檢查」。
**尚未接入轉向控制，也不是可直接啟用的大車避讓版本。** 所有輸出固定包含
`applied_offset_m: 0`、`control_eligible: false`。沒有修改 modeld、Jetlink、
控制器、Panda 或車型。後續卡車實測分支新增 offroad 自動打包程序，詳見
`openpilot/tools/clearance_shadow/README_實測資料.md`；它不會啟動辨識或偏移。

## 查到的現有實作

| 來源 | 已有的功能 | 本次使用方式 |
|---|---|---|
| [HCOP lane_offset.py](https://github.com/henryopen/openpilot/blob/d0bdf61f9c6cfa795ac7c2d789a1be2aa40cf044/openpilot/selfdrive/modeld/lane_offset.py) | 最右車道 15 cm 左偏，5 cm/s 漸變；另有 Custin 彎道學習補償 | 參考道路條件、幅度及漸變速度；重新實作觀察器，加強兩側外線消失的拒絕條件 |
| [HCOP yolod.py](https://github.com/henryopen/openpilot/blob/d0bdf61f9c6cfa795ac7c2d789a1be2aa40cf044/openpilot/yolo/yolod.py) | 辨識結果送 HUD，沒有接控制 | 沒有把它當作已完成的卡車避讓控制 |
| [twilsonco LaneOffset](https://github.com/prodigz/openpilot-twilsonco-archive/blob/f1660891c8e364b11f9518f1a907b33f4c615885/selfdrive/controls/lib/lane_planner.py) | 依左右鄰近車流選擇相反方向的車道內位置、平順轉換與車道條件 | 行為參考；該舊分支的雷達/控制器沒有整包移植 |
| [Ultralytics COCO](https://docs.ultralytics.com/datasets/detect/coco/) | 預訓練分類包括 bus、truck | 用真實 YOLO 推論；從模型名稱表取分類，不假設自訂模型一定用 COCO 編號 |
| [Ultralytics tracking](https://docs.ultralytics.com/modes/track/) | ByteTrack / BoT-SORT 等跨影格追蹤 | 明確選用 ByteTrack，要求同一 ID 持續出現才建立候選偏移 |

程式是新寫的離線觀察器；沒有移植 HCOP 的攝影機 shear，也沒有帶入別台 Custin
學到的彎道補償表。兩個模式分開比較，YOLO 沒看到大車時不會自動切成路邊偏移。

## 兩種觀察模式

`roadside`：借用 HCOP 最右車道判斷概念，但同時要求右側道路邊界可信、右外線不明顯，
以及左外線與左鄰車道寬度可信。兩側外線都看不到時，不產生候選偏移。
此幾何證據仍不能判斷左邊車道的交通方向，因此不聲稱可安全執行。

`vehicles`：以 YOLO 的 bus/truck 分類、ByteTrack ID、連續時間及近似投影位置判斷：
右側大車 → 左偏候選；左側大車 → 右偏候選。人、機車、自行車及一般車也保留，
用來阻擋往另一側偏移的候選；兩側有對象、目標跨入自己車道、框被裁切或無法定位時取消。

兩模式皆要求有效且新鮮的 Carrot 模型資料、清楚的本車道線、近直線、約 20 km/h 以上、
橫向輔助原本在工作，且沒有打燈、換道意圖或駕駛接手。需至少 0.8 秒和 4 個不同時間
的樣本確認。重複、逆序或間隔超過 0.25 秒的影格不累積確認時間。

預設候選上限 15 cm，變化率 5 cm/s；CLI 可改 `--offset-cm`、`--rate-cm-s`。
幅度只是研究參數，不是實車安全標準。範圍受本車道前方多個位置的線距、車寬包絡、
既有模型路徑與額外線距共同限制。方向反轉要先回到零。

## 執行：建議先在 Mac / 電腦離線分析

使用完整的本分支 checkout，從 repository 根目錄執行。只測試政策時需要 numpy、pytest：

```bash
python -m pytest --confcutdir=openpilot/tools/clearance_shadow/tests \
  -c openpilot/tools/clearance_shadow/pytest.ini openpilot/tools/clearance_shadow/tests
```

1. 在具備完整 Carrot Python/cereal 環境的電腦，準備同一段的 `rlog.zst` 與原始
   `fcamera.hevc`。目前不支援 qcamera、剪輯、鏡像、重新裁切或重新縮放的影片。
   匯出依 `roadEncodeIdx.segmentId` 對齊影片，用 `timestampEof` 和訊息發布時間
   只取當時已經存在的資料；不以檔名或固定 20 Hz 猜時間。

```bash
python -m openpilot.tools.clearance_shadow.export_rlog /path/to/rlog.zst \
  --output /path/to/geometry.jsonl
```

2. 在獨立 Python 環境安裝可選的 YOLO 依賴，不要裝到 C4 的駕駛環境。
   依上游說明取得可信的本地模型，例如官方 YOLO11n；模型不包含在本分支中，
   使用及再散布應遵循該模型和 Ultralytics 的授權。

```bash
python -m pip install -r openpilot/tools/clearance_shadow/requirements-yolo.txt
python -m openpilot.tools.clearance_shadow.run \
  --sidecar /path/to/geometry.jsonl --video /path/to/fcamera.hevc \
  --weights /path/to/yolo11n.pt --device cpu --mode vehicles \
  --output /path/to/vehicles.jsonl --overlay /path/to/vehicles.mp4
```

Mac 可另測 `--device mps`。這並不代表已驗證你的 Mac M4 與 Jetlink 同時執行的負載。
輸出影片固定 20 fps，只供逐格檢視；不要用它的播放時間當反應延遲證據。
JSONL 保留來源影格及時間，summary 記錄模型/影片/sidecar 的 SHA-256、推論耗時及拒絕原因。

3. 對照道路偏移，不需要 YOLO 或影片：

```bash
python -m openpilot.tools.clearance_shadow.run --mode roadside \
  --sidecar /path/to/geometry.jsonl --offset-cm 15 --rate-cm-s 5 \
  --output /path/to/roadside.jsonl
```

每次使用新的輸出檔名，以免覆蓋既有檢查結果。所有資料留在執行的電腦，不會上傳到服務。

可重現單張圖片的真實推論介面檢查：

```bash
python -m openpilot.tools.clearance_shadow.smoke_image \
  --weights /path/to/yolo11n.pt --image /path/to/bus.jpg --expect bus \
  --output /path/to/bus-smoke.json
```

同張照片跑三次只用來檢查類別讀取及追蹤 ID 介面，不能當作移動車輛追蹤成效。

## 已實作與尚未驗證

本次本機驗證：61 項自動測試通過、Ruff 與 Python 語法檢查通過。
以官方 YOLO11n 權重實際執行 Ultralytics 的 `bus.jpg`，取得 bus 分類及連續三次相同追蹤 ID。
另外完整取出 COCO128 中標有 truck 的五張圖片測試：兩張有輸出 truck，
其餘三張沒有輸出 truck；有一張的 truck 信心低於候選門檻。沒有為了讓它通過而降低門檻。
這些是訓練集/範例圖片的介面檢查，不是獨立準確率評估。結果說明此模型能產生貨車分類，
但漏判仍存在，不能把一次分類成功當成可控制車輛的證據。

- 已實作真實 YOLO 模型介面、ByteTrack 連續追蹤、HCOP 道路條件的加強版、候選政策、
  rlog 幾何匯出、錄影推論及可檢查的結果輸出。
- YOLO 的 truck 分類包含不同大小貨車；bus/truck 類別本身不等於量到大型車的實際寬度。
- 車框底部投影假設地面近似平面，坡道、車身俯仰、遮蔽、接地點不準都會影響間距。
  增加區間餘量不等於已校準的測距誤差。真正側邊、車尾盲區不在這個前鏡頭觀測範圍。
- 候選限制使用 `modelV2.position`；尚未套入現行 Carrot 所有固定/彎道偏移後的最終 MPC 路徑。
  也尚未測量 Ioniq 5 實際輪胎/車身邊界、閉迴路反應與雨夜誤判率。
- 完整 rlog/影片實車回放、C4/Jetlink 同時執行效能、實際轉向接入仍是下一階段；
  此版沒有 `--apply` 或繞過觀察模式的開關。

要接入轉向前，需要用你 Ioniq 5 的左右大車遭遇影片與同步 rlog 驗證方向、間距、遮蔽、
漏判、資料新鮮度和車道餘裕，再為車道線/MPC及模型直接轉向模式分別設計接入。
這一步不能只用通用巴士照片或合成幾何測試取代。
