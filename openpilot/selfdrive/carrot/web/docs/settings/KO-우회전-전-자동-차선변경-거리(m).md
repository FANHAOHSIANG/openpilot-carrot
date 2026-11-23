<!-- CARROT:GENERATED schema="1" locale="ko" group="STEER_LANECHANGE" param="AutoTurnControlRightLaneChange" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# 우회전 전 자동 차선변경 거리(m)

**메뉴:** 주행 제어 \> 차량 조향 \> 차로 변경 (자동 턴)

---

<!-- CARROT:SETTING:BEGIN AutoTurnControlRightLaneChange -->
<a id="AutoTurnControlRightLaneChange"></a>

## 우회전 전 자동 차선변경 거리(m)

`AutoTurnControlRightLaneChange`

0m는 끄기이며 최대 2000m까지 설정합니다. 최신 내비 정보로 고속도로·자동차전용도로가 확인되면 설정값을 사용하고, 일반도로·도로 정보 미확인 또는 만료 시에는 설정값과 500m 중 작은 거리를 사용합니다. 2000m로 설정하면 일반도로 500m·고속도로 2000m입니다. 차선 개수만으로 고속도로로 판단하지 않습니다. 기존 저장값은 유지합니다. 기존 켜짐 설정은 최초 재시작 시 250m로 전환합니다. 기존 ATC에 추가되는 기능입니다. ATC 1·2번에서 10km/h 이상이며 TBT 우회전·우측 분기까지 설정 거리 이내일 때 실제 턴 시작 전까지 우측 깜박이를 요청합니다. protocol-matched USB2CAN, BLE or Panda/SPAS 구성, AutoBlinkerControl=2, LaneChangeNeedTorque=0이 필요합니다. 후방은 유효한 차량 BSD 경고만 확인하며 코너 거리는 사용하지 않습니다. 우측 차선 전방 차량은 현재 거리와 상대속도로 예측한 3초 뒤 거리가 모두 5m 이상이어야 합니다. 전방 레이더 오류·수신 지연 시 시작하지 않습니다. 요청 전 조향은 조건 확인을 다시 시작하며, 요청 후 운전자 조향·수동 개입은 취소합니다. 10~30km/h에서 시작한 신호는 끝날 때까지 표시 전용으로 유지합니다. 30km/h 이상에서 시작한 신호만 기존 차선변경 흐름으로 연결합니다. 우측 차선부터 로드에지까지 2.5m 이상 여유가 필요합니다. 네이티브 Kick에서도 조건을 통과한 30km/h 이상 ATC 요청의 실제 점등을 기존 차선변경 판단으로 연결합니다. 표시 전용 신호와 취소 후 남은 점멸은 자동 조향에서 제외합니다. 시작 대기 4초와 기존 취소 조건은 유지하므로 최소 점멸 횟수를 보장하지 않습니다.

<!-- CARROT:AUTO:BEGIN AutoTurnControlRightLaneChange -->
<!-- CARROT:AUTO:SOURCE facts="925cf60141de277885476dad87b99c73d1bfeae1da36da4cc1d1c66c54ede573" semantic="c7837f43c48a0b5200b4346241f2335323cffcce3eff5cbf9e02db29380b7032" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **종류:** 숫자
- **기본값:** `0`
- **범위:** `0` ~ `2000`
- **변경 단위:** `50`
- **메뉴:** 주행 제어 \> 차량 조향 \> 차로 변경 (자동 턴)
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END AutoTurnControlRightLaneChange -->

<!-- CARROT:MANUAL:BEGIN AutoTurnControlRightLaneChange -->
<!-- CARROT:REVIEW reviewed-for="3008498ad9b26c4e6721da72acaa56057939a66d7d15c51954adbc9bb64b1584" reviewed-at="2026-11-02T22:15:29.542142+00:00" -->
<!-- CARROT:SECTION:BEGIN BEHAVIOR -->
### 동작

0m는 끄기이며 값을 높이면 우회전·우측 분기에 더 먼 거리부터 조건을 확인합니다. 250m는 기존 범위에 해당하며, 기존 켜짐 값은 재시작 시 250m로 전환합니다.

10km/h 이상에서 우측 차선·로드에지, 유효한 BSD와 현재 및 3초 예측 전방 거리를 확인합니다. 30km/h 미만에 시작한 신호는 표시 전용이고, 그 이상에서 시작한 신호는 기존 차선변경 판단으로 연결됩니다.
<!-- CARROT:SECTION:END BEHAVIOR -->
<!-- CARROT:MANUAL:END AutoTurnControlRightLaneChange -->

<!-- CARROT:SETTING:END AutoTurnControlRightLaneChange -->
