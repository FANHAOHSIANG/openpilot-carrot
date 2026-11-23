<!-- CARROT:GENERATED schema="1" locale="ko" group="VEH_CANFD" param="CanfdHDA2" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# CANFD HDA2지원(0)

**메뉴:** 차량·하드웨어 \> CANFD·HDA

---

<!-- CARROT:SETTING:BEGIN CanfdHDA2 -->
<a id="CanfdHDA2"></a>

## CANFD HDA2지원(0)

`CanfdHDA2`

0: HDA1, 1: HDA2. CameraSCC가 0이면 순정 HDA2 SCC 연결을 사용하며, CameraSCC 개조 설정을 켰으면 그 설정을 유지합니다. 차량·하네스에 맞게 선택하고 변경 후 재시작하세요.

<!-- CARROT:AUTO:BEGIN CanfdHDA2 -->
<!-- CARROT:AUTO:SOURCE facts="175c0a3c6560fbe90786017bbad6af5ae7327ab543d596ddbb5c2929269980aa" semantic="6b24754cbac58c945701508b8f8fc96985d82ba760a595087dd33c95e6210b76" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **종류:** 토글
- **기본값:** `0`
- **범위:** `0` ~ `1`
- **메뉴:** 차량·하드웨어 \> CANFD·HDA
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END CanfdHDA2 -->

<!-- CARROT:MANUAL:BEGIN CanfdHDA2 -->
<!-- CARROT:REVIEW reviewed-for="2cd10469d96bc08a71fdfa257929f6cf6790a84cd48e7d2bcc55c07355d65caa" reviewed-at="2026-07-24T16:44:29+09:00" -->
<!-- CARROT:SECTION:BEGIN BEHAVIOR -->
### 동작

- `0` — 현대·기아 CAN FD 차량을 HDA1 구성으로 처리합니다.
- `1` — HDA2 CAN 버스 구성을 사용합니다.
<!-- CARROT:SECTION:END BEHAVIOR -->

<!-- CARROT:SECTION:BEGIN USAGE -->
### 사용

차량의 HDA·CAN FD 구성을 확인한 뒤 정차 상태에서 설정하고, 다음 주행에서 관련 기능과 오류 유무를 확인합니다.
<!-- CARROT:SECTION:END USAGE -->

<!-- CARROT:SECTION:BEGIN REFERENCE -->
### 참고

<!-- CARROT:NOTICE level="WARNING" -->
> [!WARNING]
> 검증되지 않은 CAN FD 설정은 차량 경고등이나 CAN 오류를 일으킬 수 있습니다.
<!-- CARROT:NOTICE:END -->
<!-- CARROT:SECTION:END REFERENCE -->
<!-- CARROT:MANUAL:END CanfdHDA2 -->

<!-- CARROT:SETTING:END CanfdHDA2 -->
