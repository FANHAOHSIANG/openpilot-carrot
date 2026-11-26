# 獨立 Test 分支功能整理與整合檢查（2026-11-26）

本文件是原始碼查核紀錄，不是正式版發布公告，也不代表功能已經完成實車驗證。適用分支 `test/carrot-wip-upstream-20261104`。本次僅更新文件，不變更車控、Panda、安全限制、裝置或正式分支。

## 固定查核基準

- [獨立 Test 15a81ff8](https://github.com/FANHAOHSIANG/openpilot-carrot/commit/15a81ff840cc6a1e92519f6e0d4463e37db23f32)
- [Tony 融合 Test 5eda71aa](https://github.com/FANHAOHSIANG/openpilot-carrot/commit/5eda71aad247220246bc8b662b6d5642e9c481fb)
- [純官方鏡像 2e8908ef8](https://github.com/FANHAOHSIANG/openpilot-carrot/commit/2e8908ef8d1686d176b86c2770abd5b1b051a6a1)
- [官方 carrot-wip 47b1d349](https://github.com/ajouatom/openpilot/commit/47b1d349ca0bb26cfe99b3908d83108c0d200ad3)
- 正式 carrot-wip：acde165f（本次不修改）。

## 功能清單

| 功能 | 獨立 Test 原始碼查核結果 |
| --- | --- |
| 彎道預調速 | 設定存在：TurnSpeedControlMode、AutoCurveSpeedFactor、AutoCurveSpeedLowerLimit、OsmCurveSpeedEnabled、MapTurnSpeedFactor；未完成新版 PRE 實際調速或線性升降速驗證 |
| 自動轉彎 | AutoTurnControl、AutoTurnControlSpeedTurn、AutoTurnControlAdaptiveSpeed 等設定存在；不代表每車型均已實測 |
| 車道線模式 | UseLaneLineCurveSpeed 等設定存在；與使用者獨立的模型彎道置中不同 |
| 使用者模型彎道置中 | 尚未整合。Test 的 controlsd.py、carrot_settings.json 不含 ModelCurveCentering，curve_centering.py 無法取得；融合版三者存在 |
| ONNX 車道與盲點 | OnnxBsdEnabled 預設 0；另有置信與間隔設定；不代表車輛端額外模型已驗證 |
| 外部 HUD | ClusterHud、ClusterHudFloatingArrows、ClusterHudSpeedLimitSign、ClusterHudScreenMode 等設定存在；未完成全部 renderer、物件模型、LED 與版本一致性驗證 |
| Jetlink | Test README 記載無需另裝 carrot-jetlink 分支；既有 Mac Jetlink 0.10.1 是否與所有新功能相容，仍須以固定版本協定回歸驗證 |
| Carrot Bridge / Mac HUD | 分屬其他儲存庫；不可將 App 85 的發布或 Mac renderer 圖片視為 C4 控制功能已移植 |

## 使用者彎道置中的移植檢查

來源：[cc13575e](https://github.com/FANHAOHSIANG/openpilot-carrot/commit/cc13575e45f17f499c75e52092d4cc734d3eb6d6)，融合版另有 [297a6034](https://github.com/FANHAOHSIANG/openpilot-carrot/commit/297a60349a54aa9a2d957719c9308e2e1b4da516) Autospeed 相容修正。

目標是保留原始功能獨立開關與預設關閉，不改既有扭力／Panda 安全限制，不依賴 Mac，保留 CarrotPlanner；不把另一分支的完整 controlsd.py 或設定檔覆蓋到 Test。

原始補丁涉及 20 個檔案。以下為針對固定 Test 內容的逐段原始上下文比對（不是 git apply 成功結果）：

| 檔案 | 原始補丁上下文 |
| --- | --- |
| openpilot/cereal/log.capnp | 1/1 相符 |
| openpilot/common/params_keys.h | 1/1 相符 |
| openpilot/selfdrive/controls/controlsd.py | 4/6 相符；更新流程及模型曲率分支不同 |
| openpilot/selfdrive/carrot_settings.json | 0/2 相符；選單與參數結構不同 |
| openpilot/selfdrive/controls/tests/test_controlsd_publish.py | 1/1 相符 |
| openpilot/selfdrive/controls/tests/test_lateral_startup_control.py | 2/3 相符；fixture 已變動 |
| Settings-Catalog.json | 查詢回傳 404；須核對生成流程與路徑 |

因此不得以直接 cherry-pick 或整檔覆蓋的方式宣稱移植完成。需重新建立候選、保留既有分支行為，依當前 schema 生成文件；離線回放、模型曲率與控制回歸、原廠安全測試、開關關閉等價性和失效退出驗證全部通過後才能考慮合併。未完成前不列為可用功能。

## 上游與其他候選

- [PR #82](https://github.com/FANHAOHSIANG/openpilot-carrot/pull/82)：舊 Test 基底 9526ef4b，PR 顯示可合併不等同 CI 通過；應重新核對基底與最新官方。
- [PR #86](https://github.com/FANHAOHSIANG/openpilot-carrot/pull/86)：HKG 扭力研究草稿，舊基底；保持離線審查，不視為已發布。
- 官方 47b1d349 與純官方鏡像 2e8908ef8 不同；最新官方涉及 Hyundai CAN-FD 轉向佇列及安全測試。需固定來源、檢查相容性與 CI，不能用舊 PR 的結果替代新版驗證。
- 本輪未執行完整 CI、實車或 OTA，未更新官方鏡像與控制程式。
