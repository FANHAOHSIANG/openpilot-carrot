<!-- CARROT:GENERATED schema="1" locale="ko" group="CRUISE_GAP" param="DrivingPlannerMode" -->
<!-- CARROT:AUTHORING guide="https://github.com/ajouatom/openpilot/blob/carrot-wip/tools/docs/wiki_settings/AUTHORING_GUIDE.md" editable="CARROT:MANUAL only" -->
# 주행 플래너

**메뉴:** 주행 제어 \> 크루즈·차간 \> 차간거리

---

<!-- CARROT:SETTING:BEGIN DrivingPlannerMode -->
<a id="DrivingPlannerMode"></a>

## 주행 플래너

`DrivingPlannerMode`

다음 주행부터 적용. 자동 설정은 지원 차량에서 Alpha 종방향 제어를 켤 수 있으며 일부 차량은 순정 AEB 또는 레이더가 비활성화됩니다.

<!-- CARROT:AUTO:BEGIN DrivingPlannerMode -->
<!-- CARROT:AUTO:SOURCE facts="bd8768dfda21831128a6c5d3ff471f644625f69e4f116412ccd516de5f4b8f3c" semantic="315a98e2ff21614bb87598630f8bff17e2c46f6243467cb229b50f4c84cd51af" review="needs_review" -->
<!-- CARROT:SECTION:BEGIN OVERVIEW -->
- **종류:** 선택
- **기본값:** CarrotPlanner (`0`)
- **범위:** CarrotPlanner (`0`) ~ 순수 비전 (차량 자동 설정) (`3`)
- **변경 단위:** `1`
- **선택지:** `0` CarrotPlanner, `1` openpilot Autospeed, `2` 순수 비전 E2E (실험), `3` 순수 비전 (차량 자동 설정)
- **메뉴:** 주행 제어 \> 크루즈·차간 \> 차간거리
<!-- CARROT:SECTION:END OVERVIEW -->
<!-- CARROT:AUTO:END DrivingPlannerMode -->

<!-- CARROT:MANUAL:BEGIN DrivingPlannerMode -->
<!-- CARROT:REVIEW reviewed-for="" -->
<!-- CARROT:MANUAL:END DrivingPlannerMode -->

<!-- CARROT:SETTING:END DrivingPlannerMode -->
