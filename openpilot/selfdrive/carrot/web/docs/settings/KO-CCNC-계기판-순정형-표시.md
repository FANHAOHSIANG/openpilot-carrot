<!-- CARROT:GENERATED schema="1" locale="ko" group="VEH_CANFD" param="CcncClusterDisplay" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# CCNC 계기판 순정형 표시

**메뉴:** 차량·하드웨어 \> CANFD·HDA

---

<!-- CARROT:SETTING:BEGIN CcncClusterDisplay -->
<a id="CcncClusterDisplay"></a>

## CCNC 계기판 순정형 표시

`CcncClusterDisplay`

0: 끔(기본), 1: 켬. 0은 아래 항목만 끕니다. HDP 차간 표시·팝업, 측면 박스→회색 차, 정차 중 조향 아이콘 수정은 이 설정과 무관하게 항상 적용됩니다. 적용: 현대·기아·제네시스 CAN-FD에서 카메라 SCC에 오픈파일럿 롱컨(HyundaiCameraSCC 1·2)을 쓰고, 카메라의 CCNC 계기판 프레임 0x161(HDP 아이콘은 0x162)을 받은 차량. 오픈파일럿이 그 프레임을 바꿔 다시 보내며, 순정 HDA2처럼 오픈파일럿 상태를 계기판에 보여 줍니다. 약 1초 안에 반영됩니다. - 차선: 모델 차선 확률이 1초 넘게 0.08 미만이고 카메라도 그 선을 못 보면 그 선을 그리지 않습니다(0.12 이상이면 다시 그림, 주황 선은 유지). 아이오닉9·EV9는 기존 차선 표시를 유지합니다. - 점선: 카메라가 점선으로 본 차선을 점선으로 그립니다(아이오닉5 PE·그랜저 GN7·EV4). - 차로 강조: 조향 중 상태에 따라 차로 색을 바꿉니다. 레인리스 초록, 레인모드 하늘색, 조향각 오차 0.3초 이상 노랑, 조향 한계 빨강, 차로변경 중 초록. 숨긴 차선이 있으면 바꾸지 않습니다. - 앞차 링: 앞차가 보이면 크루즈 중에는 파란 링을 오픈파일럿 목표 차간 거리에, 크루즈가 아닐 때는 흰 링을 표시합니다. - 팝업: 크루즈를 켜거나 끌 때 순정 안내 팝업을 2초 띄웁니다. - 경고 문구: 오픈파일럿 경고 일부(속도 과다, 조향·SCC 작동 불가, 조향 한계, CAN·센서 이상)를 순정 문구로 띄웁니다. 조향 한계(주변 확인) 문구에는 순정처럼 더블 차임을 1초 냅니다. DBC에 없는 문구는 아이오닉5 PE·그랜저 GN7·EV4에만 나옵니다. - HDP 아이콘: 크루즈 또는 조향 중 HDP 아이콘을 켭니다(아이오닉5 PE·그랜저 GN7·EV4).

<!-- CARROT:AUTO:BEGIN CcncClusterDisplay -->
<!-- CARROT:AUTO:SOURCE facts="ebd20d28e36207d4809fadf4fbb6aa20cf94b8b715ca6835999d6c0ad894d616" semantic="51f05ac1b11c155f7bc0190c1fc950a3b08c18761a77b6a68f9ed9e16b394137" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **종류:** 토글
- **기본값:** `0`
- **범위:** `0` ~ `1`
- **메뉴:** 차량·하드웨어 \> CANFD·HDA
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END CcncClusterDisplay -->

<!-- CARROT:MANUAL:BEGIN CcncClusterDisplay -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END CcncClusterDisplay -->

<!-- CARROT:SETTING:END CcncClusterDisplay -->
