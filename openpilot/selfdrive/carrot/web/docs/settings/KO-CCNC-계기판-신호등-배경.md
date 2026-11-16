<!-- CARROT:GENERATED schema="1" locale="ko" group="VEH_CANFD" param="CcncTrafficBackground" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# CCNC 계기판 신호등 배경

**메뉴:** 차량·하드웨어 \> CANFD·HDA

---

<!-- CARROT:SETTING:BEGIN CcncTrafficBackground -->
<a id="CcncTrafficBackground"></a>

## CCNC 계기판 신호등 배경

`CcncTrafficBackground`

0: 끔(기본, 배경은 기존 그대로), 1: 켬. 0은 이 항목만 끕니다(항상 적용되는 계기판 수정은 「CCNC 계기판 순정형 표시」 참고). 오픈파일럿이 신호등을 감지하면 CCNC 계기판 배경을 바꿉니다. 빨간불은 감지되는 동안 빨간 배경, 초록불은 바뀐 뒤 2초만 초록 배경입니다. 기기 화면 신호등 표시와 같은 판단(longitudinalPlan.trafficState)을 씁니다. 신호 배경이 크루즈·회전 배경보다 우선합니다. - 적용: 「CCNC 계기판 순정형 표시」와 같은 차량(현대·기아·제네시스 CAN-FD에서 카메라 SCC에 오픈파일럿 롱컨(HyundaiCameraSCC 1·2)을 쓰고, 카메라의 CCNC 계기판 프레임 0x161을 받은 차량). 약 1초 안에 반영됩니다. - 배경 값 5(빨강)·8(초록)은 DBC에 없는 값으로, 아이오닉5 PE 계기판에서 확인했습니다.

<!-- CARROT:AUTO:BEGIN CcncTrafficBackground -->
<!-- CARROT:AUTO:SOURCE facts="f0ffb1916a72dc7447be8f4bb652a50110326330a8215d4fcdc425ec75865f93" semantic="a384d27d552cb1006f160c4f53c1c2198356bc1f61e0b307e0a7710e03354404" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **종류:** 토글
- **기본값:** `0`
- **범위:** `0` ~ `1`
- **메뉴:** 차량·하드웨어 \> CANFD·HDA
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END CcncTrafficBackground -->

<!-- CARROT:MANUAL:BEGIN CcncTrafficBackground -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END CcncTrafficBackground -->

<!-- CARROT:SETTING:END CcncTrafficBackground -->
