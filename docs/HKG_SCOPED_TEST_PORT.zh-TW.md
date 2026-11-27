# Tony HKG 功能分階段移植（獨立 Test）

來源固定：Tony/carrot-wip ee68edadc8ef3e05379ca05d0240eb55b182eb51；獨立 Test 基底 b7b505e0ac8a5da139d0e50b319877171e2bea3a。

- HkgPhase1Assist：純模型路徑低速反應及高速平滑、直接 ACC 的彎道速度上限；預設關閉，不改動既有扭力設定、車道線路徑及 Panda。
- LowSpeedSteerObserveOnly：被動紀錄，預設關閉，不調高扭力或斜率。不是 Tony 完整 LowSpeedSteerReserve。
- 原始 Panda CAN-FD steering check 的拒絕分支有註解掉的 tx=false，故保留完整扭力功能待安全審核，不擴張控制權限；需另外驗證修復後的硬體相容與 B1 客製訊號。
- 此次未實車驗證，不建議道路啟用；既有彎道置中及 Offroad 開關保持。
