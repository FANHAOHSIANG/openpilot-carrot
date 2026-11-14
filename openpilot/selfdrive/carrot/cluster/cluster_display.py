from __future__ import annotations

import math


CLUSTER_LANGUAGE_EN = "en"
CLUSTER_LANGUAGE_KO = "ko"
CLUSTER_LANGUAGE_ZH_TW = "zh-TW"
KPH_TO_MPH = 0.621371192237334
METERS_TO_FEET = 3.280839895013123
METERS_PER_MILE = 1609.344

_TEXT = {
    CLUSTER_LANGUAGE_EN: {
        "driving_report": "DRIVING REPORT",
        "trip_summary": "TRIP SUMMARY",
        "time": "TIME",
        "distance": "DISTANCE",
        "average_speed": "AVG SPEED",
        "max_speed": "MAX SPEED",
        "auto_drive": "AUTO DRIVE",
        "max_accel": "MAX ACCEL",
        "max_decel": "MAX DECEL",
        "hard_accel": "HARD ACCEL",
        "hard_brake": "HARD BRAKE",
        "hard_corner": "HARD CORNER",
        "system": "SYSTEM",
        "device_angle": "DEVICE ANGLE",
        "driving_mode_eco": "ECO",
        "driving_mode_safe": "SAFE",
        "driving_mode_normal": "NORMAL",
        "driving_mode_sport": "SPORT",
        "navigation": "NAVIGATION",
        "next": "NEXT",
        "section": "SECTION",
        "average": "AVG",
        "route": "ROUTE",
        "connected": "CONNECTED",
        "waiting": "WAITING",
        "off_route": "OFF ROUTE",
        "openpilot_unavailable": "openpilot Unavailable",
        "waiting_to_start": "Waiting to start",
        "take_control_immediately": "TAKE CONTROL IMMEDIATELY",
        "system_unresponsive": "System Unresponsive",
        "reboot_device": "Reboot Device",
    },
    CLUSTER_LANGUAGE_KO: {
        "driving_report": "주행리포트",
        "trip_summary": "주행 요약",
        "time": "시간",
        "distance": "거리",
        "average_speed": "평균속도",
        "max_speed": "최고속도",
        "auto_drive": "자동주행",
        "max_accel": "최대가속",
        "max_decel": "최대감속",
        "hard_accel": "급가속",
        "hard_brake": "급감속",
        "hard_corner": "급코너",
        "system": "시스템",
        "device_angle": "디바이스 설치각",
        "driving_mode_eco": "연비",
        "driving_mode_safe": "안전",
        "driving_mode_normal": "일반",
        "driving_mode_sport": "고속",
        "navigation": "내비게이션",
        "next": "다음",
        "section": "구간",
        "average": "평균",
        "route": "경로",
        "connected": "연결됨",
        "waiting": "연결 대기",
        "off_route": "경로 이탈",
        "openpilot_unavailable": "openpilot 사용 불가",
        "waiting_to_start": "시작 대기 중",
        "take_control_immediately": "즉시 운전대를 잡으세요",
        "system_unresponsive": "시스템 응답 없음",
        "reboot_device": "기기를 재부팅하세요",
    },
}

_TEXT[CLUSTER_LANGUAGE_ZH_TW] = {'driving_report': '駕駛資訊',
 'trip_summary': '行程摘要',
 'time': '時間',
 'distance': '距離',
 'average_speed': '平均速度',
 'max_speed': '最高速度',
 'auto_drive': '輔助駕駛',
 'max_accel': '最大加速',
 'max_decel': '最大減速',
 'hard_accel': '急加速',
 'hard_brake': '急煞車',
 'hard_corner': '急轉彎',
 'system': '系統',
 'device_angle': '裝置安裝角度',
 'driving_mode_eco': '節能',
 'driving_mode_safe': '安全',
 'driving_mode_normal': '一般',
 'driving_mode_sport': '運動',
 'navigation': '導航',
 'next': '下一個',
 'section': '區間',
 'average': '平均',
 'route': '路線',
 'connected': '已連線',
 'waiting': '等待連線',
 'off_route': '偏離路線',
 'openpilot_unavailable': 'openpilot 無法使用',
 'waiting_to_start': '等待啟動',
 'take_control_immediately': '請立即接手駕駛',
 'system_unresponsive': '系統無回應',
 'reboot_device': '請重新啟動裝置'}


def normalize_cluster_language(value: object, default: str = CLUSTER_LANGUAGE_EN) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", "ignore")
    normalized = str(value or "").strip().lower().removeprefix("main_")
    if normalized in ("zh-tw", "zh-cht", "zh-hant", "zh_hant", "zh_tw"):
        return CLUSTER_LANGUAGE_ZH_TW
    if normalized in ("ko", "kr", "kor", "korean"):
        return CLUSTER_LANGUAGE_KO
    if normalized in ("en", "eng", "english"):
        return CLUSTER_LANGUAGE_EN
    return default if default in _TEXT else CLUSTER_LANGUAGE_EN


def normalize_metric_setting(value: object, default: bool = True) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bytes):
        value = value.decode("utf-8", "ignore")
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("", "none"):
            return bool(default)
        return normalized not in ("0", "false", "off", "no")
    return bool(value)


def cluster_text(language: str, key: str) -> str:
    normalized = normalize_cluster_language(language)
    return _TEXT[normalized].get(key, _TEXT[CLUSTER_LANGUAGE_EN].get(key, key))


def display_speed(speed_kph: int | float, is_metric: bool) -> float:
    speed = float(speed_kph)
    if not math.isfinite(speed):
        return 0.0
    return speed if is_metric else speed * KPH_TO_MPH


def speed_unit(is_metric: bool) -> str:
    return "km/h" if is_metric else "mph"


def format_radar_distance(distance_m: int | float, is_metric: bool) -> str:
    distance = max(0.0, float(distance_m))
    if is_metric:
        return f"{distance:.0f} m"
    return f"{distance * METERS_TO_FEET:.0f} ft"


def format_navi_distance(distance_m: int | float, is_metric: bool) -> str:
    distance = max(0.0, float(distance_m))
    if is_metric:
        if distance < 1000.0:
            return f"{int(round(distance))} m"
        if distance < 10_000.0:
            return f"{distance / 1000.0:.1f} km"
        return f"{distance / 1000.0:.0f} km"

    miles = distance / METERS_PER_MILE
    if miles < 0.1:
        return f"{distance * METERS_TO_FEET:.0f} ft"
    if miles < 10.0:
        return f"{miles:.1f} mi"
    return f"{miles:.0f} mi"


def format_trip_distance(distance_m: int | float, is_metric: bool) -> str:
    distance = max(0.0, float(distance_m))
    if is_metric:
        if distance < 1000.0:
            return f"{distance:.0f} m"
        if distance < 10_000.0:
            return f"{distance / 1000.0:.2f} km"
        return f"{distance / 1000.0:.1f} km"

    miles = distance / METERS_PER_MILE
    if miles < 0.1:
        return f"{distance * METERS_TO_FEET:.0f} ft"
    if miles < 10.0:
        return f"{miles:.2f} mi"
    return f"{miles:.1f} mi"


# Exact display labels only: never replace substrings inside road names or protocol fields.
HUD_ZH_LABELS = {'확인 중': '檢查中',
 '저장소 없음': '找不到儲存庫',
 '브렌치 아님': '未位於分支',
 '원격 설정 없음': '未設定遠端',
 '원격에서 삭제됨': '遠端已刪除',
 '원격 확인 실패': '遠端檢查失敗',
 'pull 확인 실패': '更新檢查失敗',
 'SIGNAL VIEW: ROAD CAMERA ONLY': '號誌觀察：僅道路攝影機',
 'PREVIOUS': '前次辨識',
 'LIVE': '即時',
 'WAITING': '等待資料',
 'STOP': '即將停車',
 'CAM': '測速照相',
 'SECTION': '區間測速',
 'ACCEL': '加速',
 'STEER': '轉向',
 '좌회전': '左轉',
 '우회전': '右轉',
 '직진': '直行',
 '유턴': '迴轉',
 '목적지': '目的地',
 '경로 이탈': '偏離路線',
 'Turn left': '左轉',
 'Turn right': '右轉',
 'Continue straight': '直行',
 'U-turn': '迴轉',
 'ATC': '自動轉彎',
 'TBT': '轉向提示',
 'NOO': '導航輔助',
 '가속': '加速',
 '조향': '轉向',
 '정지 예정': '即將停車',
 '카메라': '測速照相',
 '구간': '區間測速',
 '커브': '彎道',
 '구간단속': '區間測速',
 '방지턱': '減速丘',
 '어린이': '學校區域',
 '경찰': '警察',
 '도로제한': '道路速限',
 '경로': '路線',
 '모델': '模型',
 '에코': '節能',
 '감속': '減速',
 '맑음': '晴朗',
 '구름조금': '晴時多雲',
 '안개': '霧',
 '눈': '下雪',
 '비': '下雨',
 '뇌우': '雷雨',
 '흐림': '陰天'}


def localize_hud_text(language: str, text: str) -> str:
    if normalize_cluster_language(language) != CLUSTER_LANGUAGE_ZH_TW:
        return text
    for key, value in _TEXT[CLUSTER_LANGUAGE_ZH_TW].items():
        if text in (_TEXT[CLUSTER_LANGUAGE_EN].get(key), _TEXT[CLUSTER_LANGUAGE_KO].get(key)):
            return value
    if text in HUD_ZH_LABELS:
        return HUD_ZH_LABELS[text]
    for prefix, translated in (("git pull 가능 +", "可更新 +"), ("SIGNAL CANDIDATES ", "號誌候選 "), ("avg ", "平均 ")):
        if text.startswith(prefix):
            suffix = text[len(prefix):]
            if suffix.isdecimal():
                return translated + suffix
    # Known ATC/TBT messages retain the source and direction, without guessing arbitrary prose.
    for prefix in ("ATC: ", "TBT: ", "ATC ", "TBT "):
        if text.startswith(prefix) and text[len(prefix):] in HUD_ZH_LABELS:
            return HUD_ZH_LABELS[prefix[:3]] + "：" + HUD_ZH_LABELS[text[len(prefix):]]
    return text


# Exact stock alert translations, paired by msgid from app_ko.po/app_zh-CHT.po.
HUD_ZH_LABELS.update({'Cancel': '取消',
 'Device': '裝置',
 'Driving Personality': '駕駛風格',
 'Enable': '啟用',
 'Error': '錯誤',
 'HIGH': '高',
 'LTE': 'LTE',
 'Longitudinal Maneuver Mode': '縱向操作模式',
 'NO': '否',
 'Open': '開啟',
 'RESET': '重設',
 'Reboot': '重新啟動',
 'TAKE CONTROL IMMEDIATELY': '請立刻接手控制',
 'TEMP': '溫度',
 'Unknown': '未知',
 'default': '預設',
 'down': '下',
 'km/h': 'km/h',
 'left': '左',
 'mph': 'mph',
 'now': '現在',
 'openpilot Unavailable': 'openpilot 無法使用',
 'openpilot 사용 불가': 'openpilot 無法使用',
 'right': '右',
 'up': '上',
 '기본값': '預設',
 '높음': '高',
 '롱컨 기동 모드': '縱向操作模式',
 '사용': '啟用',
 '아니오': '否',
 '아래': '下',
 '알수없음': '未知',
 '열기': '開啟',
 '오류': '錯誤',
 '오른쪽': '右',
 '온도': '溫度',
 '왼쪽': '左',
 '위': '上',
 '장치': '裝置',
 '재설정': '重設',
 '재시작': '重新啟動',
 '주행 성향': '駕駛風格',
 '즉시 수동 조작하세요': '請立刻接手控制',
 '지금': '現在',
 '취소': '取消'})

HUD_ZH_LABELS.update({
    "Turning Left": "正在左轉", "좌회전 합니다": "正在左轉",
    "Turning Right": "正在右轉", "우회전 합니다": "正在右轉",
    "Turn Exceeds Steering Limit": "轉彎超出轉向能力",
    "회전이 조향 한도를 초과함": "轉彎超出轉向能力",
    "Confirm Lane Change": "請確認變換車道",
    "MAP STREAM WAITING": "等待地圖畫面",
    "MAP STREAM STALLED": "地圖畫面中斷",
    "WAITING FOR NEXT FRAME": "等待下一張畫面",
})
