<!-- CARROT:GENERATED schema="1" locale="ko" group="INDICATOR_AUTO" param="AutoBlinkerControl" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# 깜박이 자동제어

**메뉴:** 차량·하드웨어 \> 깜박이 제어 \> 자동 점등

---

<!-- CARROT:SETTING:BEGIN AutoBlinkerControl -->
<a id="AutoBlinkerControl"></a>

## 깜박이 자동제어

`AutoBlinkerControl`

0: 끄기(블루투스 원터치 유지). 1: 5km/h 이하 블루투스 입력을 회전 완료까지 유지하고 ATC audioTurn 알림 시점부터 교차로 정차 중에도 유지하며 실제 회전 후 핸들이 중앙으로 돌아오면 자동 해제. 2: 1번 + ATC 차선변경이 실제 시작될 때부터 완료까지 점멸(대기 중 제외). 같은 방향 버튼으로 유지 취소, 반대 버튼으로 전환. 순정 레버 우선. 지원하는 젯슨 USB-CAN/B1 차량 전용. ATC는 전송 확인 후 미점등일 때 한 번만 재요청합니다. 유효한 TBT 좌표·차량 GPS로 직진 통과가 확인되면 자동 취소합니다. 위치가 불확실하면 위치 기반 취소는 사용하지 않습니다. TBT 턴은 audioTurn 당시 거리와 이동 거리로 턴 지점 이후 30m를 추적합니다. 단 해당 방향 조향 30도 초과 및 차체 회전 20도 이상을 확인한 뒤, 1km/h 이상에서 핸들이 ±15도 안으로 돌아오면 즉시 유지 요청을 종료합니다. 턴 진입 전 신호 대기에서는 유지합니다. 새 다음 턴 안내는 현재 턴 완료 후 이어받으며, 해당 방향으로 30도 이상 조향한 뒤 운전자가 반대 토크로 조향각을 반대쪽 0도 너머로 넘기면 취소합니다. 전송 승인과 점등을 확인한 TBT 신호는 수신부 driver\_override만으로 해제하지 않습니다. 순정 램프의 즉시 소등은 보장하지 않습니다. 크루즈 CANCEL을 누르면 자동 깜빡이 요청과 유지가 중단됩니다. 주차 중 핸들을 돌려도 새로 켜지지 않으며, SET/RES 또는 +/−로 기존 크루즈 취소 상태를 해제하면 새 동작부터 재개합니다. 직접 쓰는 레버와 블루투스 깜빡이 버튼은 계속 사용할 수 있습니다. 지원되는 Panda/SPAS 출력에서도 같은 설정과 판단을 사용합니다. Panda/SPAS 출력은 차종명 제한 없이 ECAN의 SPAS 0x165(24바이트)·0x16A(32바이트)와 레버 0x3C1(8바이트)가 확인된 카메라 SCC CAN-FD 구성에서 선택할 수 있습니다. USB2CAN·BT2CAN의 확인된 TBT 유지에는 기존 수신기 driver\_override 처리를 적용합니다. Panda/SPAS에서 확인한 실제 레버 조작은 TBT 유지도 종료합니다.

<!-- CARROT:AUTO:BEGIN AutoBlinkerControl -->
<!-- CARROT:AUTO:SOURCE facts="41b836df506c2230cc95f161b42a1b035c549af2b2eaf459b5ec380725e42490" semantic="bec8c1e7a73c7c63379074f9c07dc8771b558a21feef757c841b15a77a5172ac" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **종류:** 구간 선택
- **기본값:** `0`
- **범위:** `0` ~ `2`
- **변경 단위:** `1`
- **메뉴:** 차량·하드웨어 \> 깜박이 제어 \> 자동 점등
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END AutoBlinkerControl -->

<!-- CARROT:MANUAL:BEGIN AutoBlinkerControl -->
<!-- CARROT:REVIEW reviewed-for="edd05659292aebc71be712906d3faaadf71c30551e5a372287abb2bf65bd60ca" reviewed-at="2026-11-10T10:39:14.889272+00:00" -->
<!-- CARROT:SECTION:BEGIN BEHAVIOR -->
### 동작

지원 차량에서 BT·ATC의 실제 깜박이 요청과 유지 상태를 관리합니다.

TBT 턴은 실제 회전 진입을 확인한 뒤 이동 중 핸들이 ±15도 이내로 돌아오면 정상 종료합니다. 턴 지점 이후 이동 거리도 종료 판단에 사용합니다. 해당 방향으로 30도 이상 조향한 뒤 운전자가 반대 토크로 0도를 넘어 반대 방향으로 꺾으면 취소합니다.

전송 승인과 점등을 확인한 TBT 신호는 수신부 driver_override 상태에서도 턴 종료까지 유지합니다. 최초 전송 승인이 없는 경우에는 유지 출력을 시작할 수 없습니다. 새 다음 턴 안내는 현재 턴 완료 후 이어받습니다.

크루즈 CANCEL을 누르면 자동 깜빡이 요청과 유지가 중단됩니다. 주차 중 핸들을 돌려도 새로 켜지지 않으며, SET/RES 또는 +/−로 기존 크루즈 취소 상태를 해제하면 새 동작부터 재개합니다. 직접 쓰는 레버와 블루투스 깜빡이 버튼은 계속 사용할 수 있습니다.
<!-- CARROT:SECTION:END BEHAVIOR -->
<!-- CARROT:MANUAL:END AutoBlinkerControl -->

<!-- CARROT:SETTING:END AutoBlinkerControl -->
