"""Small, paced bitmap effects for the LOY real-time drawing mode."""
import colorsys
import re

from PIL import ImageChops

KINDS = ("left", "right", "decel", "pause_thanks", "thanks", "traffic")
EFFECTS = ("static", "blink", "scroll_left", "scroll_right", "breathe", "double_blink", "rainbow")


def defaults(texts, colors):
    return {kind: {"text": texts[kind], "color": colors[kind], "effect": "static", "speed": 1}
            for kind in KINDS}


def validate(settings):
    if not isinstance(settings, dict) or set(settings) != set(KINDS):
        raise ValueError("請填寫每種車況的顯示設定")
    result = {}
    for kind in KINDS:
        item = settings[kind]
        if not isinstance(item, dict):
            raise ValueError("顯示設定格式錯誤")
        text, color, effect, speed = (item.get(k) for k in ("text", "color", "effect", "speed"))
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 16:
            raise ValueError("文字請輸入 1–16 個字")
        if any(not (32 <= ord(c) <= 126 or 0x3400 <= ord(c) <= 0x9fff
                    or 0xff01 <= ord(c) <= 0xff60
                    or c in "，。！？、：；「」『』（）《》…—") for c in text):
            raise ValueError("文字請使用中英文、數字或常用標點")
        if not isinstance(color, str) or not re.fullmatch(r"[0-9a-fA-F]{6}", color):
            raise ValueError("顏色格式錯誤")
        if effect not in EFFECTS or type(speed) is not int or speed not in (1, 2, 3):
            raise ValueError("特效或速度設定錯誤")
        result[kind] = {"text": text.strip(), "color": color.lower(), "effect": effect, "speed": speed}
        if "weight" in item:
            if item["weight"] not in ("normal", "bold"):
                raise ValueError("字體粗細設定錯誤")
            result[kind]["weight"] = item["weight"]
    return result


def signature(style, tick):
    effect, speed = style["effect"], style["speed"]
    if effect == "static":
        return 0
    step = tick * speed
    if effect == "blink":
        return (step // 2) % 2
    if effect == "double_blink":
        return int(step % 8 in (0, 2))
    if effect in ("breathe", "rainbow"):
        return step % (8 if effect == "breathe" else 12)
    return step


def render(mask, style, tick):
    effect = style["effect"]
    phase = signature(style, tick)
    rgb = tuple(bytes.fromhex(style["color"]))
    if effect == "blink" and phase == 1:
        return None, bytes(rgb)
    if effect == "double_blink" and phase == 0:
        return None, bytes(rgb)
    if effect in ("scroll_left", "scroll_right"):
        distance = (phase * 2) % mask.width
        mask = ImageChops.offset(mask, -distance if effect == "scroll_left" else distance, 0)
    elif effect == "breathe":
        factor = (0.20, 0.35, 0.60, 0.85, 1.0, 0.85, 0.60, 0.35)[phase]
        rgb = tuple(round(c * factor) for c in rgb)
    elif effect == "rainbow":
        rgb = tuple(round(c * 255) for c in colorsys.hsv_to_rgb(phase / 12, 1, 1))
    return mask, bytes(rgb)
