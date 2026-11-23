<!-- CARROT:GENERATED schema="1" locale="ko" group="INDICATOR_AUTO" param="ManualTurnIndicator" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# 수동 턴 자동깜박이(시험)

**메뉴:** 차량·하드웨어 \> 깜박이 제어 \> 자동 점등

---

<!-- CARROT:SETTING:BEGIN ManualTurnIndicator -->
<a id="ManualTurnIndicator"></a>

## 수동 턴 자동깜박이(시험)

`ManualTurnIndicator`

운전자의 조향력과 핸들 회전, 실제 차체 회전을 함께 확인해 좌·우 턴의 깜박이를 켭니다. ATC 설정과 독립적으로 동작하며 차선이 흐린 교차로에서도 감지합니다. 시작 속도 5~60km/h, 같은 방향 조향력 0.15초, 조향각 42도 이상 및 22도 이상 증가, 같은 방향 차체 회전 조건을 확인합니다. 핸들 ±15도 복귀와 회전 안정화 또는 운전자 반대 조향으로 종료하며 최대 30초 유지합니다. 기본 꺼짐. 규격이 확인된 USB2CAN·BLE·Panda/SPAS 장치와 자동 깜박이 제어 1·2번에서 동작합니다. 주차장 코너에서도 켜질 수 있으며 도로 곡선·회피 동작의 오점등 가능성과 실차 점등 검증이 남아 있습니다. 수동 차선변경 표시 중 같은 방향의 수동 턴 조건이 충족되면 기존 요청을 이어받아 턴 종료까지 추적합니다. 교차로의 차선 위치 급변은 조향력·조향각 증가·실제 회전으로 확인하는 수동 턴 감지를 초기화하지 않습니다. 이미 켜진 신호는 D단 정차 확인 중 차속 추정값이 0 부근에서 미세하게 음수로 흔들려도 유지합니다. 지원되는 Panda/SPAS 출력에서도 같은 설정과 판단을 사용합니다. Panda/SPAS 출력은 차종명 제한 없이 ECAN의 SPAS 0x165(24바이트)·0x16A(32바이트)와 레버 0x3C1(8바이트)가 확인된 카메라 SCC CAN-FD 구성에서 선택할 수 있습니다. 수동 차로변경·회전의 정상 완료가 빨라도 Panda/SPAS 출력은 첫 송신 요청부터 최소 2초 유지합니다. 실제 레버 조작, 취소, 입력·차선 오류에는 즉시 종료합니다. 실제 점멸 횟수는 차량에 따라 달라집니다. 이전 수동 턴이 반대 조향으로 끝나면 10km/h 이상에서 다음 반대 턴의 최근 조향을 제한적으로 이어받습니다. 재점등 직전 0.25초의 각도 변화만 이어받고, 기존 2초 대기·연속 1초 소등 및 현재 같은 방향 조향 조건을 확인합니다. 3초 안에 이어지지 않으면 버리며 기존 새 조향 감지는 별도로 유지합니다. 수동 차선 접근 신호가 2초 이내 복귀·차선 재배정으로 끝났어도, 같은 방향의 수동 턴은 별도로 확인할 수 있습니다. 종료 당시 같은 방향 조향 중이고 3초 안에 10km/h 이상에서 새 턴의 조향각 증가·차체 회전 조건을 만족해야 합니다. 운전자 레버·취소·입력 오류는 이 복구를 막습니다. 재점등 대기 중 턴 조건이 이미 확인되고 핸들 회전이 정점에 도달했다면, 같은 방향 조향력·차체 회전이 계속되는 동안 정점 후 최대 0.3초·5도 이내의 작은 풀림을 이어받습니다. 기존 재점등 대기는 유지하며, 대기가 끝난 뒤 다시 각도가 증가하면 새 조향 감지를 사용합니다. 조향력 해제·반대 조향·도로 곡선 판정은 이 정점 기억을 지웁니다.

<!-- CARROT:AUTO:BEGIN ManualTurnIndicator -->
<!-- CARROT:AUTO:SOURCE facts="c5be7541ea6be10f0869f8fa173ca059c49e37ccbe42f8bebb748e9378da7102" semantic="d97a40a90b8c179facde86b6376a8ee85dbad1ab6c1ba3c99c7b0b44f5a208f2" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **종류:** 토글
- **기본값:** `0`
- **범위:** `0` ~ `1`
- **메뉴:** 차량·하드웨어 \> 깜박이 제어 \> 자동 점등
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END ManualTurnIndicator -->

<!-- CARROT:MANUAL:BEGIN ManualTurnIndicator -->
<!-- CARROT:REVIEW reviewed-for="e08aa7e7e006ddb909a0060571a3f7983d6c70f1249f7f29cc42c19e87f3451a" reviewed-at="2026-11-14T02:05:14Z" -->
<!-- CARROT:SECTION:BEGIN BEHAVIOR -->
### 동작

운전자의 같은 방향 조향력과 핸들 각도 증가, 신선한 차체 회전을 함께 확인해 턴을 표시합니다. ATC 설정과 횡제어 활성 여부에 관계없이 동작하며, 램프 피드백은 자동조향 요청에서 차단합니다.

핸들 복귀와 회전 안정화로 종료하고 반대 방향으로 직접 조향하면 취소합니다. 입력 오류와 설정 끄기도 요청을 종료합니다.
다음 수동 턴은 직전 표시의 마지막 유지 시점에서 2초가 지나고 양쪽 램프가 연속 1초 꺼진 뒤 새로 감지합니다. 두 조건은 동시에 확인합니다.
수동 차선 지시 중 같은 방향 수동 턴 조건이 충족되면 기존 요청과 확인 응답을 유지하며 턴 완료 조건으로 추적합니다. 새 탭 요청이 아닙니다.
<!-- CARROT:SECTION:END BEHAVIOR -->

<!-- CARROT:SECTION:BEGIN USAGE -->
### 사용

Git Pull 후 콤마를 재시작하고 이 옵션을 켭니다. 아이오닉5 PE의 지원 깜박이 장치와 자동 깜박이 제어 1·2번에서 사용합니다.
<!-- CARROT:SECTION:END USAGE -->

<!-- CARROT:SECTION:BEGIN REFERENCE -->
### 참고

주차장 통로·경사로·주차 진입도 감지될 수 있습니다. 차선이 흐린 곡선과 회피 동작의 오점등 가능성이 남아 있으며 실차 점등 검증이 필요합니다.

[한국어 동작 조건](https://github.com/ajouatom/openpilot/blob/carrot-wip/docs/user/ko/lane-change.md)
<!-- CARROT:SECTION:END REFERENCE -->

<!-- CARROT:MANUAL:END ManualTurnIndicator -->

<!-- CARROT:SETTING:END ManualTurnIndicator -->
