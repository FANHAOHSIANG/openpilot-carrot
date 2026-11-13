# 全台離線 OSM 彎道預覽

目標分支：`FANHAOHSIANG/openpilot-carrot` 的 `test/truck-clearance-204f9cca`。
接續 `37abaf2c` 的導航幾何彎速控制。這次增加沒有目的地、沒有導航 polyline 時的本機道路來源。

## 使用方式

1. 將 C4 更新至包含本次修改的測試分支並重新啟動。
2. Carrot Web → 設定 → 速度／減速 → 彎道與轉彎：`全台離線 OSM 彎道預覽`（`OsmCurveSpeedEnabled`）預設開啟。
3. `TurnSpeedControlMode=2` 使用視覺與地圖幾何兩者的較低上限；模式 3 只採幾何彎速，但仍須通過近端視覺配對。模式 0／1 不使用 OSM 彎速。本次不覆寫既有模式選擇。
4. 停車、保持 C4 開機，連上非計量 Wi-Fi，程式會自動下載全部圖資包。各包完成後即保留，無須每次開車輸入指令。
5. 已下載地區可離線使用。第一次尚未下載、缺少鄰接圖資或無法確認道路時，不會新增 OSM 減速要求。

## 涵蓋全台，不限北部

| 範圍 | 包含 |
| --- | --- |
| 台灣本島 | 北、中、南、東部及恆春半島 |
| 澎湖 | 澎湖群島 |
| 金門 | 大小金門及烏坵涵蓋區 |
| 馬祖 | 南北竿、莒光、東引涵蓋區 |
| 東南離島 | 綠島、蘭嶼所在涵蓋區 |

來源採用 [pfeiferj/mapd](https://github.com/pfeiferj/mapd) 預先製作的 OpenStreetMap 道路圖資。
`GROUPS` 設定 8 個兩度資料包，下載後只保留上述範圍的四分之一度圖磚。
2026-11-11 已實際下載、檢查全部 8 包，保留 165 個圖磚，SQLite 快取合計 59.96 MiB。
資料大小隨來源更新改變；下載流量大於保留後的快取，因為部分資料包也含周邊非目標區域。
北台灣是開發時第一個驗證樣本，並非功能範圍。

道路資料 © OpenStreetMap contributors，依 [ODbL](https://www.openstreetmap.org/copyright) 提供。
圖磚格式參考 mapd `e220ccca60bec1e620454ed59e70bff15919f10b` 的 `offline.capnp`，保留 MIT 授權於 `osm_map_LICENSE.txt`。
圖資沒有放進 Git，也不會把目前 GPS 座標傳給下載伺服器。功能不使用 Mapbox 計費 API。

## 計算與來源優先順序

- 有選定的導航 polyline：繼續使用原本導航幾何。OSM 不取代導航路線。
- 沒有 polyline：用最新 GPS、行進方向及本機道路圖找出唯一候選。
- 向前最多取足夠計算 500 公尺彎速的走廊。遇到多個可行出口就停在岔路，不用道路名稱、等級或「較直」猜目的地。
- 同時讀取預覽範圍內的鄰接圖磚，避免跨圖磚時漏掉支路。單行道尊重圖資方向。
- 候選道路需再次通過現有 `RouteCurveSpeed` 的近端視覺、位置、方向與多影格確認，才產生距離式速度上限。
- 彎道變緩時，每秒最多放寬 3.6 km/h 的幾何上限；實際加速仍取決於跟車、設定速度、視覺及縱向規劃。

同一走廊保留穩定識別碼，避免每跨過一個道路節點就重啟確認。道路無效或背景程序中止時，既有幾何上限短暫維持再漸退；手動關閉 OSM 開關立即移除 OSM 上限。

此道路走廊只供速度預覽。它不會寫入 `navRoute`、設定導航目的地、提供導航模型的轉彎指示、控制方向燈或改變轉向。
即使 CP 只投屏、沒有送 polyline，仍能獨立使用 OSM；這並不代表已經取得 Google 的導航路線。

## 背景執行與圖資維護

`osmd` 由 manager 在裝置上自動啟動，使用獨立 Python 程序、一般排程與小核心，最多 5 Hz，不使用 GPU。
CarrotMan 只以約 5 Hz 交換有大小限制的原子共享記憶體 JSON；網路、圖資解壓、SQLite 與道路圖建立均在背景程序內。
程序中止時，回覆會過期；`osmd` 不是必須在線的駕駛控制程序，因此其缺席不額外觸發控制系統的 `processNotRunning` 脫離。

下載僅在設定開啟、停車及非計量 Wi-Fi 時進行。每個下載區塊與圖磚處理都重新檢查狀態，出發或斷線時暫停。
單次網路讀取最長逾時 10 秒；暫停不是 TCP 層即時斷流，但下載絕不占用控制執行緒。
每包須通過大小、路徑、圖磚範圍、完整 64 圖磚、Cap’n Proto 解碼及 gzip CRC 檢查，再原子替換快取。
失敗不覆蓋上一份完整資料，5 分鐘後可重試；下載完成 30 天後嘗試更新，超過 90 天不再使用。
這是下載快取時間，並非每條道路的實測或 OSM 編輯日期。

快取：`/data/media/0/carrot_osm`。一般分支更新不會刪除它。
診斷：`/dev/shm/carrot_osm/response.json`；關機後共享記憶體自然清除。

查看狀態，不會啟動另一個背景程序：

```sh
cd /data/openpilot
python -m openpilot.selfdrive.carrot.osmd --status
```

| 狀態 | 意義 |
| --- | --- |
| `maps_ready` | 全部 8 包都在更新期限內 |
| `downloading_24_120` 等 | 正在下載其中一包；不是只下載這個地區 |
| `waiting_wifi` / `download_wait` | 等待適合下載的連線／重試時機 |
| `download_paused` / `download_error:...` | 暫停或下載失敗，已完成資料保留 |
| `navigation_priority` | 有導航 polyline 或模式未要求 OSM |
| `road_matched` | 道路候選已送出，仍需視覺彎速確認 |
| `ambiguous_road` / `off_road` | 無法確認唯一行進道路 |
| `stale_position` / `map_unavailable:...` | 定位過期或所需圖資不可用 |

`carrotMan.szPosRoadName` 記錄 `rc=osm/road_matched/matched:距離m/彎速kph/e誤差` 時，代表 OSM 幾何已通過視覺確認。
最後勝出的 `desiredSource` 保留既有名稱 `route`，讓下游的滑行、駕駛覆寫等政策仍辨識為幾何減速。
若另一來源要求更慢，最終來源可能仍是 `vturn`、`road` 等。

## 驗證與限制

94 項曲線、來源選擇、完整控制方法與 OSM 單元／整合測試通過。
新增測試包含全台與離島覆蓋、無目的地提前減速、單行道、支路截斷、平行道路歧義、穩定走廊、跨圖磚、缺鄰圖、快取過期、程序回覆過期、不同程序識別、下載中斷／CRC／路徑錯誤保留舊檔、導航優先與開關即時取消。
完整控制方法測試使用正式 `CarrotMan.carrot_navi_route`、`CarrotServ` 與真實 cereal 訊息，但隔離平台 IPC 與程序啟動。

實際圖資檢查已讀取台北、新竹、恆春、澎湖、金門、馬祖及東引道路，不只用合成地圖。
桌面台北／新竹密集圖磚第一次載入約 0.3–0.5 秒，單次道路配對約 11–15 ms，均在背景程序。
這些數據不是 C4 效能測試，也不是使用者原始 rlog 的實車重播結果；C4 啟動、實際減速時機與乘坐感受仍待驗證。

OSM 是道路中心線，沒有可靠的車道級位置；圖資可能過時、過疏或缺路。此格式也未保留完整的節點 ID、層級與禁轉關係。
平行路／高架道路、路口、定位偏差及過疏彎道可能讓功能不參與，不能承諾每個彎都會提前減速。
視覺與其他速度上限仍照原有設定運作；本次不改動模型、卡車辨識、CAN、AEB 或 FCA。

重跑：

```sh
PYTHONPATH=. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest \
  --confcutdir=openpilot/selfdrive/carrot/tests -c /dev/null \
  openpilot/selfdrive/carrot/tests/test_osm_curve.py \
  openpilot/selfdrive/carrot/tests/test_route_curve.py \
  openpilot/selfdrive/carrot/tests/test_route_curve_integration.py \
  openpilot/selfdrive/carrot/tests/test_curve_speed.py -q
```

回復方式：關閉 `OsmCurveSpeedEnabled` 即停用這項補充來源，原本導航幾何仍可使用；`TurnSpeedControlMode=1` 則僅保留視覺彎速。
若需回復整個本次程式變更，上一個分支基底是 `37abaf2cf3fc0434ce6dad2d1e0cc3145c0a35a6`，包含原先已整合的卡車功能與導航幾何修正。
