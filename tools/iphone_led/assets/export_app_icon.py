#!/usr/bin/env python3
"""Export the shared desktop icon into iOS and Android packaging formats.

Usage: python3 assets/export_app_icon.py [square master PNG]
Without an argument, re-export Android assets from the committed iOS master.
Requires Pillow. Does not alter LED content or app behavior.
"""
import json
from pathlib import Path
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "ios/Resources/Assets.xcassets"
ICON = CATALOG / "AppIcon.appiconset"
RES = ROOT / "android/app/src/main/res"
MASTER = ICON / "CarrotLED-1024.png"


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content + "\n")


def png(image, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)


def main():
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else MASTER
    image = Image.open(source).convert("RGB")
    if image.width != image.height:
        raise ValueError("App icon master must be square")
    image = image.resize((1024, 1024), Image.Resampling.LANCZOS)
    # Reduce unused generated texture colors; retain opaque RGB for Apple.
    if source.resolve() != MASTER.resolve():
        image = image.quantize(colors=256, dither=Image.Dither.NONE).convert("RGB")
        png(image, MASTER)
    write(CATALOG / "Contents.json", json.dumps({"info": {"author": "xcode", "version": 1}}, indent=2))
    write(ICON / "Contents.json", json.dumps({
        "images": [{"filename": MASTER.name, "idiom": "universal", "platform": "ios", "size": "1024x1024"}],
        "info": {"author": "xcode", "version": 1},
    }, indent=2))

    # Separate adaptive layer; inset the complete artwork for the 66/108 safe zone.
    foreground = Image.new("RGB", (432, 432), "#081329")
    foreground.paste(image.resize((296, 296), Image.Resampling.LANCZOS), (68, 68))
    png(foreground, RES / "drawable-nodpi/carrot_led_foreground.png")
    for density, pixels in [("mdpi", 48), ("hdpi", 72), ("xhdpi", 96), ("xxhdpi", 144), ("xxxhdpi", 192)]:
        png(image.resize((pixels, pixels), Image.Resampling.LANCZOS), RES / f"mipmap-{density}/ic_launcher.png")
    write(RES / "values/icon_colors.xml", '<resources><color name="carrot_icon_background">#081329</color></resources>')
    for version in (26, 33):
        monochrome = '\n  <monochrome android:drawable="@drawable/carrot_led_monochrome"/>' if version >= 33 else ""
        write(RES / f"mipmap-anydpi-v{version}/ic_launcher.xml", f'''<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
  <background android:drawable="@color/carrot_icon_background"/>
  <foreground android:drawable="@drawable/carrot_led_foreground"/>{monochrome}
</adaptive-icon>''')
    print("Exported opaque 1024px iOS icon, 5 Android densities, adaptive and themed icon resources")


if __name__ == "__main__":
    main()
