<!-- CARROT:GENERATED schema="1" locale="ko" group="STEER_LANEMODE" param="ModelCurveCentering" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# 모델 커브 중앙 보정

**메뉴:** 주행 제어 \> 차량 조향 \> 레인모드

---

<!-- CARROT:SETTING:BEGIN ModelCurveCentering -->
<a id="ModelCurveCentering"></a>

## 모델 커브 중앙 보정

`ModelCurveCentering`

CAN-FD 아이오닉 5의 모델 조향 모드에서 양쪽 차선이 뚜렷하고 예측 경로가 커브 안쪽으로 치우칠 때 차로 중앙 쪽으로 조향 목표를 보정합니다. 기본값은 꺼짐입니다.

<!-- CARROT:AUTO:BEGIN ModelCurveCentering -->
<!-- CARROT:AUTO:SOURCE facts="cbdb4161b3bfe3bef44abcf394da0831b22cdd65ca6eb9013c4f719d454485f4" semantic="93bb71bdc261b9cd8a21ddbe3c2243f790b32d7b9141d440191bda6e9e442b20" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **종류:** 토글
- **기본값:** `0`
- **범위:** `0` ~ `1`
- **메뉴:** 주행 제어 \> 차량 조향 \> 레인모드
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END ModelCurveCentering -->

<!-- CARROT:MANUAL:BEGIN ModelCurveCentering -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END ModelCurveCentering -->

<!-- CARROT:SETTING:END ModelCurveCentering -->
