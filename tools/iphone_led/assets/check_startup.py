"""Validate actual iOS/Android startup resources and one-shot playback duration."""
from pathlib import Path
from PIL import Image
from io import BytesIO
import json

r = Path(__file__).resolve().parents[1]
a, b = r/'android/app/src/main/assets/startup', r/'ios/Resources/Startup'
colors = [(0,0,0),(255,126,0),(93,224,20),(255,211,0)]
for width in (64,96):
    raw = (a/f'startup{width}.bin').read_bytes()
    assert raw == (b/f'startup{width}.bin').read_bytes()
    assert len(raw) == width*16*48 and max(raw) == 3
    frames = [raw[n*width*16:(n+1)*width*16] for n in range(48)]
    assert frames[0] == frames[11] and frames[0] != frames[24]
    assert not any(frames[-1]) and len(set(frames)) > 12
    # Start artwork has the same un-stretched 24x16 dimensions at both widths.
    xs = [i%width for i,v in enumerate(frames[0]) if v]
    assert max(xs)-min(xs)+1 == 20
gif = (a/'startup_car.gif').read_bytes()
assert gif == (b/'startup_car.gif').read_bytes() and len(gif) <= 8192
im = Image.open(BytesIO(gif)); assert im.size == (64,16) and 'loop' not in im.info
raw = (a/'startup64.bin').read_bytes(); duration = 0
for n in range(im.n_frames):
    im.seek(n)
    expected = bytes(channel for value in raw[(duration//50)*1024:(duration//50+1)*1024] for channel in colors[value])
    assert im.convert('RGB').tobytes() == expected
    duration += im.info['duration']
assert duration == 2400 and not any(im.convert('RGB').tobytes())
for name in ['startup_scenarios.csv','startup_gif.csv']:
    assert (r/'ios/tests'/name).read_bytes() == (r/'android/tests'/name).read_bytes()
catalog = r/'ios/Resources/Assets.xcassets/AppIcon.appiconset'
for icon in json.loads((catalog/'Contents.json').read_text())['images']:
    img = Image.open(catalog/icon['filename']); assert img.size == (1024,1024) and img.mode == 'RGB'
print('Both panel geometries, identical resources, native one-shot GIF, startup fixtures and opaque icon passed')
