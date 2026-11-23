<!-- CARROT:GENERATED schema="1" locale="ko" group="INDICATOR_AUTO" param="ManualLaneChangeIndicator" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# 수동 차선변경 깜박이(시험)

**메뉴:** 차량·하드웨어 \> 깜박이 제어 \> 자동 점등

---

<!-- CARROT:SETTING:BEGIN ManualLaneChangeIndicator -->
<a id="ManualLaneChangeIndicator"></a>

## 수동 차선변경 깜박이(시험)

`ManualLaneChangeIndicator`

수동 차선변경 자동깜박이는 좌측 차선 색상·중앙선 분류와 우측 로드에지 거리로 점등을 제한하지 않습니다. 5km/h 이상, 같은 방향 조향 의도와 실제 차선 접근, 차로 폭·경계 연속성·최근 차선 신뢰도 조건은 유지합니다. 자동조향은 요청하지 않습니다. 2초 이내 끝난 접근 신호 뒤에도 같은 방향의 실제 수동 턴을 별도로 확인해 새 요청을 만들며, 반대 방향의 새 차선접근은 연속 1초 소등 후 다시 확인할 수 있습니다. 운전자 레버·반대 램프·입력 오류·취소가 우선하며 자동조향 피드백 격리는 유지합니다. 중앙선 접근이나 도로 밖으로 움직이는 경우에도 표시될 수 있습니다.

<!-- CARROT:AUTO:BEGIN ManualLaneChangeIndicator -->
<!-- CARROT:AUTO:SOURCE facts="648d06fdef1b1528b529a7005e3e679abfaa3f8c18048a53510414ecc3a699ea" semantic="b054132b7f6fb71e55d9758b1d6cdc54cb75fac679420524d7691e6c8c56817a" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **종류:** 토글
- **기본값:** `0`
- **범위:** `0` ~ `1`
- **메뉴:** 차량·하드웨어 \> 깜박이 제어 \> 자동 점등
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END ManualLaneChangeIndicator -->

<!-- CARROT:MANUAL:BEGIN ManualLaneChangeIndicator -->
<!-- CARROT:REVIEW reviewed-for="d96432b8f8ff840459f65cab076ba12f6d57b1d333e585a4be25652182e1e7ba" reviewed-at="2026-11-14T02:05:14Z" -->
<!-- CARROT:SECTION:BEGIN BEHAVIOR -->
### 동작

최근 운전자 조향 의도와 연속적인 차선 접근을 확인하여 표시합니다. 접근 시작 시 대상 차선 신뢰도 10% 이상을 확인하고, 좌측 중앙선·우측 로드에지 제외 조건을 적용합니다.

요청 후에는 완료·복귀·입력 오류를 추적하며 자동 조향 요청을 만들지 않습니다. 종료 요청 뒤에도 순정 원터치 점멸은 남을 수 있습니다.
측정한 차선 접근 속도로 0.3초 뒤를 예측하여 점등 시점을 앞당깁니다. 차체 중심과 대상 경계의 거리 기준은 기존 0.9m에서 최대 1.2m까지만 앞당기며, 실제 0.15m 접근·운전자 의도·양쪽 경계의 일관된 이동 조건은 유지합니다.

수동·모델 표시 요청이 보낸 짧은 원터치 피드백은 요청 시각·방향·레버 카운터가 일치할 때만 제한적으로 구분합니다. 반대 방향·레버 고정 조작·수신기의 운전자 개입 판정은 취소하며, 점등이 전송 완료 응답보다 먼저 보이면 짧게 기억한 뒤 일치하는 응답을 받아 유지합니다. 같은 방향을 아주 짧은 송신 구간에 직접 누른 경우에는 이 정보만으로 완전히 구별할 수 없습니다.
시속 5km부터 운전자가 옆 차선에 실제로 접근할 때 해당 방향의 깜빡이를 요청합니다.
경계 복귀가 0.15초 지속되어야 접근 추적을 취소하며, 복귀 중에는 새 점등을 보류합니다. 최근 운전자 의도와 차로 폭이 유지되는 양쪽 경계 이동이 확인되면 제한된 위치 변화에서도 접근을 이어갑니다.

B1 릴리스 5는 확인된 자체 탭 피드백이 점멸의 소등 구간에도 이어지는 것을 허용합니다. 탭 후 중립 피드백은 허용을 닫고 이후 레버 입력은 소유권을 취소합니다. 반대 램프·원시 운전자 입력·CAN 오류·임대 만료는 계속 취소 조건입니다. 소프트웨어 리플레이는 실차 유지·취소 검증이 아닙니다.
<!-- CARROT:SECTION:END BEHAVIOR -->
<!-- CARROT:MANUAL:END ManualLaneChangeIndicator -->

<!-- CARROT:SETTING:END ManualLaneChangeIndicator -->
