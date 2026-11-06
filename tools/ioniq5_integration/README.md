# IONIQ 5 三分支整合試驗

基底是 [使用者的 Carrot WIP](https://github.com/FANHAOHSIANG/openpilot-carrot/commit/334a4ac52379f8e4aa0783d6637f34046d2ba892)。
候選來源為 [HCOP](https://github.com/FANHAOHSIANG/sunnypilot/commit/1283b4d3c7d33958ae82ffdbd1b346c1eed4e474) 及
[HKG Enhanced Jetlink](https://github.com/FANHAOHSIANG/sunnypilot/commit/872cfd28a8c20c9ec0beeb7953d5823b6da37be6)。

| 項目 | 來源 | 驗證方式 |
| --- | --- | --- |
| C4 車型設定、Mac N16 Jetlink、現有外接 HUD、Google 分享／Mapbox 導航 | Carrot 基底 | 保留既有整合，任何後續改動都和基底比較 |
| 依模型預測曲率提前減速 | HCOP CurveV2 | 對同一批路段做影子運算，核對減速時點、幅度與誤觸發 |
| 低速出彎回正與轉向扭力 | HKG Enhanced | 從同一份 rlog 比較回正後反向修正、扭力變化與車道追蹤，再挑可單獨移植的部分 |
| MADS、ACC 行為 | HKG Enhanced | 逐項驗證踏板、巡航退出和狀態轉換；等使用者選定行為 |
| FCA／AEB | 車輛與各分支的驗證條件 | 先確認原廠資料、比對 ECU 與 Panda 行為，停在離線驗證 |

## 整合試驗內容

- LED 取自 iPhone LED 測試分支 `0f6aab88`，含 C4 的唯讀橋接、iPhone
  Xcode 專案、Mac 顯示工具與測試。C4 橋接沿用來源分支的啟動條件，
  車輛上電且存在本機 `/data/iphone-led/token` 才會啟動。配對請依
  [iPhone 說明](../iphone_led/ios/README_繁體中文.txt)或[Mac 說明](../iphone_led/mac/README_繁體中文.txt)。
- `replay_candidates.py` 讀完整 cereal rlog，在電腦上計算 HCOP CurveV2 的
  加速度上限，並在符合低速條件的記錄上列出 HKG v1 的名義比例增益。
  另外使用明確標記的合成事件測試 HKG MADS 與巡航狀態轉換。
- 比較資料不接入任何行車控制。HKG 名義增益不是方向盤扭力，也不含
  NNLC、摩擦模型或完整控制器回放。MADS／巡航範例從事件層開始，
  不把放開煞車、按鍵或原廠 ECU 訊號猜成重新啟用事件。
- 原有 FCA／AEB 的行為需分開驗證。Henry／YOLO HUD 已取消。

```sh
python3 tools/ioniq5_integration/replay_candidates.py
python3 tools/ioniq5_integration/replay_candidates.py --rlog /path/to/rlog.zst --schema-dir /path/to/full-cereal-schema
```

第二個命令需要 `numpy`、`pycapnp`、`zstandard`。schema 目錄須可解析
`log.capnp` 與全部相依匯入，包括錄製版本的 `car.capnp`。
HCOP 實作源自 `1283b4d3`。HKG 狀態機與增益表源自 `872cfd28`，
採用僅供離線輸入的事件介面。原始授權見 [HKG 授權](LICENSE-HKG.md)。

This software is licensed under a custom license requiring permission for use.
This project uses software from Haibin Wen and SUNNYPILOT LLC and is licensed under a custom license requiring permission for use.

## 已做的比對

同一份使用者的 IONIQ 5 停車 CAN 摘要，Carrot 實車參數為
`hyundaiCanfd/6173`。HCOP 和 HKG 都推導為 LFA 加 Camera SCC，
縱向選項關閉和開啟分別得到 `9`、`13`。HKG 基礎參數原先為
`radarUnavailable=true`，Sunnypilot 的 Camera SCC 延伸層改成
`false`。這個旗標不證明實體前雷達已被正確解碼。採樣沒有 ECU
韌體資料，所有推導只作程式比對。

## 重跑

在電腦環境準備各供體乾淨的 opendbc checkout，使用相容的 Python 及該
opendbc 所需套件。每次執行只匯入一個供體。

```sh
python3 tools/ioniq5_integration/compare_parked.py parked.json --source hcop --opendbc /path/to/henryopen-opendbc
python3 tools/ioniq5_integration/compare_parked.py parked.json --source hkg --opendbc /path/to/hkg-opendbc
```

`parked.json` 是 HCOP 試驗分支的停車觀察程式輸出。
[觀察程式說明](https://github.com/FANHAOHSIANG/sunnypilot/blob/ce3b81a79b3222f5e29f0a9bd320f2d06e0deae9/tools/ioniq5/README.zh-TW.md)
。供體 opendbc 分別固定為 [HCOP](https://github.com/henryopen/opendbc/tree/40181738da3f695e679eff3feef028074153e759)
與 [HKG](https://github.com/TonyBinheWu/opendbc/tree/1c51731784729da5ebaf24b3c34106bd27aaf94b)。
本工具不執行車輛初始化或發送 CAN，結果不能作為上車驗證。
