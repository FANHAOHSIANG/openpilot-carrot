<!-- CARROT:GENERATED schema="1" locale="ko" group="INDICATOR_OUTPUT" param="CanfdBlinkerKick" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# Panda/SPAS 깜박이 출력

**메뉴:** 차량·하드웨어 \> 깜박이 제어 \> 출력 장치

---

<!-- CARROT:SETTING:BEGIN CanfdBlinkerKick -->
<a id="CanfdBlinkerKick"></a>

## Panda/SPAS 깜박이 출력

`CanfdBlinkerKick`

Panda를 통해 차량 SPAS 메시지로 공통 깜박이 요청을 송신합니다. 기본 꺼짐. 아이오닉5 PE·아이오닉9·그랜저 GN7의 카메라 SCC CAN-FD 구성에서 지원합니다. 자동 점등은 「깜박이 자동제어」와 「수동 차선변경 깜박이」·「수동 회전 깜박이」·모델 관찰 설정을 따릅니다. 점등 시작·유지·종료는 USB2CAN·BT2CAN과 같은 공통 판단을 사용합니다. 자동 깜박이 0에서는 자동 요청이 꺼지며 D단에서 명시적인 블루투스 깜박이 버튼은 단발 요청으로 처리합니다. 켜기는 다음 OnRoad 시작부터, 끄기는 즉시 적용됩니다. 갱신된 Panda 펌웨어가 필요합니다. 켜면 USB2CAN·BT2CAN 출력이 중단되며 외부 명령 만료와 독점 소유권을 확인한 후 송신합니다. 다음 OnRoad 시작 때 기존 CanfdBlinkerControl을 끕니다. 실제 레버 조작은 자동 출력을 중단합니다. 자동 램프 피드백은 조향 요청과 격리하며 검증된 실제 레버 입력은 우선 처리합니다. 공통 요청 종료 시 SPAS 송신을 종료하고 ECU 기본 세션을 복구합니다. 실제 램프의 잔여 점멸 시간은 차량에 따라 달라집니다. 기존 저장값과 공통 자동 점등 설정은 그대로 사용합니다. 이전 모델 차로변경 전용 횟수 설정은 제거되었으며 점등 조건은 공통 설정에서 선택합니다. 수동 차로변경·회전의 정상 완료가 빨라도 Panda/SPAS 출력은 첫 송신 요청부터 최소 2초 유지합니다. 실제 레버 조작, 취소, 입력·차선 오류에는 즉시 종료합니다. 실제 점멸 횟수는 차량에 따라 달라집니다.

<!-- CARROT:AUTO:BEGIN CanfdBlinkerKick -->
<!-- CARROT:AUTO:SOURCE facts="4670e5102d6d151bc3147d2a06d770e408537095a7e8e03113cfaa6b8e371cb1" semantic="e3d01ebf21844e839abfc47d5fc08878416a9261d5535df9497959b72b96c157" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **종류:** 토글
- **기본값:** `0`
- **범위:** `0` ~ `1`
- **메뉴:** 차량·하드웨어 \> 깜박이 제어 \> 출력 장치
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END CanfdBlinkerKick -->

<!-- CARROT:MANUAL:BEGIN CanfdBlinkerKick -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END CanfdBlinkerKick -->

<!-- CARROT:SETTING:END CanfdBlinkerKick -->
