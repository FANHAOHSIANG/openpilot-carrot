"""Exact 16-row pixel adaptation of the approved carrot-car icon.

Native iPixel GIF: 64x16, 20 fps. LOY fallback: the same indexed frames at
96x16, paced by transport readiness at a maximum 5 fps. No image streaming
is needed in native mode. The final frame is blank and the GIF plays once.
"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
COLORS = [(0, 0, 0), (255, 126, 0), (93, 224, 20), (255, 211, 0)]
SPRITE = [
    '...........22...........',
    '........2..22..2........',
    '.........222222.........',
    '......111111111111......',
    '.....11111111111111.....',
    '....1100000000000011....',
    '...110033003300330011...',
    '..11100330033003300111..',
    '..11100000000000000111..',
    '...111111111111111111...',
    '...113331111111133311...',
    '...111111111211111111...',
    '...111110000000011111...',
    '...111111100001111111...',
    '....1111111111111111....',
    '....1111........1111....',
]
assert all(len(row) == 24 for row in SPRITE)
PALETTE = [n for color in COLORS for n in color] + [0] * (768 - 12)
COUNT, DELAY = 48, 50


def frame(width, index):
    out = Image.new('P', (width, 16)); out.putpalette(PALETTE)
    if index >= 46: return out
    # Hold the complete logo for 600 ms, then shrink into the distance and
    # move to the right. Keep its aspect ratio on both 64 and 96 columns.
    progress = max(0, min(1, (index - 12) / 34))
    ease = progress * progress * (3 - 2 * progress)
    size = max(3, round(16 * (1 - .80 * ease)))
    sprite = Image.new('P', (24, 16)); sprite.putpalette(PALETTE)
    sprite.putdata([0 if c == '.' else int(c) for row in SPRITE for c in row])
    sprite = sprite.resize((max(4, round(size * 1.5)), size), Image.Resampling.NEAREST)
    x = round((width - sprite.width) / 2 + ease * (width / 2 + 9))
    y = round((16 - size) / 2 - 2 * ease)
    out.paste(sprite, (x, max(0, y)))
    return out


def main():
    targets = [ROOT/'android/app/src/main/assets/startup', ROOT/'ios/Resources/Startup']
    for target in targets: target.mkdir(parents=True, exist_ok=True)
    for width in (64, 96):
        images = [frame(width, n) for n in range(COUNT)]
        raw = b''.join(im.tobytes() for im in images)
        for target in targets: (target/f'startup{width}.bin').write_bytes(raw)
        if width == 64:
            path = targets[0]/'startup_car.gif'
            # No NETSCAPE loop extension: play once, leave a blank final frame.
            images[0].save(path, save_all=True, append_images=images[1:], duration=DELAY,
                           optimize=False, disposal=1, palette=images[0].getpalette())
            data = path.read_bytes(); assert len(data) <= 8192
            (targets[1]/path.name).write_bytes(data)
        previews = [im.convert('RGB').resize((width*8, 128), Image.Resampling.NEAREST) for im in images]
        previews[0].save(ROOT/f'design/startup-{width}x16.gif', save_all=True,
                         append_images=previews[1:], duration=DELAY, loop=0)
    print('Generated startup frames, one-shot GIF and both panel previews')


if __name__ == '__main__': main()
