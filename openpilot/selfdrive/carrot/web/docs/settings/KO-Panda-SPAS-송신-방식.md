<!-- CARROT:GENERATED schema="1" locale="ko" group="INDICATOR_OUTPUT" param="CanfdBlinkerKickMode" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# Panda/SPAS 송신 방식

**메뉴:** 차량·하드웨어 \> 깜박이 제어 \> 출력 장치

---

<!-- CARROT:SETTING:BEGIN CanfdBlinkerKickMode -->
<a id="CanfdBlinkerKickMode"></a>

## Panda/SPAS 송신 방식

`CanfdBlinkerKickMode`

「Panda/SPAS 깜박이 출력」이 깜빡이 명령을 보내는 방식입니다. 기본 1. 0: 자동주차 ECU가 멈춤 요청에 답하고 순정 SPAS 송신이 멈춘 뒤에만 보냅니다. 답이 없으면 켜지 않습니다(아이오닉5 PE는 답하지 않았습니다). 1: 피기백. ECU가 답하지 않으면 panda가 우리 SPAS 프레임을 순정 SPAS 프레임 바로 뒤에 붙여 보냅니다. 같은 ID가 동시에 송신을 시작하지 않아 충돌 오류를 막습니다. ECU가 답하면 0과 같습니다. - 대상 차량·배선은 「Panda/SPAS 깜박이 출력」과 같습니다. 1번에서 ECU 무응답을 확인한 뒤 순정 SPAS 수신과 출력 소유권이 계속 정상이라면, 확인 시점부터 60초 동안 다음 요청의 0.4초 응답 대기를 반복하지 않습니다. 수신 중단·새 ECU 응답·출력 소유권 상실·설정 변경·시간 만료 시 다시 확인합니다. 0번은 항상 ECU 응답이 필요하며 순정 프레임 동기화와 운전자 취소 조건은 유지합니다.

<!-- CARROT:AUTO:BEGIN CanfdBlinkerKickMode -->
<!-- CARROT:AUTO:SOURCE facts="a4819ecb4316ef3d9ed80ef587f3adc218a073f0b8a51dd86de83cfc10635300" semantic="70568faca97452808ebd34cfcdcab63fc7b42577cc2420a1aeaf4adf8e066b41" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **종류:** 토글
- **기본값:** `1`
- **범위:** `0` ~ `1`
- **메뉴:** 차량·하드웨어 \> 깜박이 제어 \> 출력 장치
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END CanfdBlinkerKickMode -->

<!-- CARROT:MANUAL:BEGIN CanfdBlinkerKickMode -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END CanfdBlinkerKickMode -->

<!-- CARROT:SETTING:END CanfdBlinkerKickMode -->
