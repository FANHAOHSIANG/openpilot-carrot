"""Procedural Sasuke-inspired LED transformations. No downloaded images.

64x16, 20fps/3.2s, fixed 16-color global palette. Reset is hidden in a blink.
Sasuke's anatomical left eye is on the viewer's right (x >= 32).
"""
from pathlib import Path
import math
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
NAMES = ['sasuke_sharingan', 'sasuke_rinnegan']
FRAMES, DELAY = 64, 50
COLORS = [
    (0,0,0), (27,22,34), (70,49,65), (104,7,25),
    (194,12,38), (255,34,54), (255,106,122), (42,12,69),
    (88,33,137), (148,77,217), (198,140,250), (229,194,255),
    (250,225,240), (176,27,105), (160,54,166), (56,2,13),
]
PALETTE = [c for rgb in COLORS for c in rgb]


def ease(x):
    x = max(0, min(1, x))
    return x*x*(3-2*x)


def tomoe(x, y, radius, angle):
    # Head plus tapered tangential tail; deliberately large enough for 16 rows.
    cx, cy = radius*math.cos(angle), radius*math.sin(angle)
    dx, dy = x-cx, y-cy
    radial = dx*math.cos(angle)+dy*math.sin(angle)
    tangent = -dx*math.sin(angle)+dy*math.cos(angle)
    return dx*dx+dy*dy < .78**2 or (0 < tangent < 1.6 and abs(radial+.34*tangent) < .42*(1-tangent/1.9))


def sharingan(x, y, angle):
    r = math.hypot(x,y)
    if r > 6.35: return COLORS[1]
    if r < 1.15 or abs(r-3.9)<.33: return COLORS[0]
    if any(tomoe(x,y,3.8,angle+k*2*math.pi/3) for k in range(3)): return COLORS[0]
    return COLORS[3 if r>5.6 else 5]


def mangekyo(x, y, angle):
    r = math.hypot(x,y)
    if r > 6.35: return COLORS[1]
    if r < 1.15: return COLORS[0]
    theta = math.atan2(y,x)-angle
    # Six tapered red points, black iris and pupil; the inverted color pattern.
    a = abs((theta+math.pi/6) % (math.pi/3)-math.pi/6)
    boundary = (6.5*1.8)/(1.8*math.cos(a)+(6.5-3.6*math.cos(math.pi/6))*math.sin(a))
    if r < boundary: return COLORS[5]
    return COLORS[3] if r>5.8 else COLORS[0]


def rinnegan(x, y):
    r=math.hypot(x,y)
    if r>6.35:return COLORS[1]
    if r<.85 or any(abs(r-ring)<.35 for ring in [1.65,3.55,5.5]):return COLORS[7]
    for radius,shift in [(2.65,-math.pi/2),(4.6,-math.pi/6)]:
        if any(tomoe(x,y,radius,shift+k*2*math.pi/3) for k in range(3)):return COLORS[7]
    return COLORS[10 if r<5.0 else 9]


def mix(a,b,t):
    return tuple(round(x+(y-x)*t) for x,y in zip(a,b))


def frame(mode,n):
    effective = 0 if n>=60 else n
    change = ease((effective-16)/16)
    # Stable start, rotating morph, then a clearly readable completed form.
    rotation = math.pi/6 + math.pi/3*ease((effective-6)/26)
    open_amount = [1,.75,.4,.03,.03,.4,.75,1][n-56] if n>=56 else 1
    im=Image.new('P',(64,16));im.putpalette(PALETTE)
    for y in range(16):
        for x in range(64):
            side=x//32;u=x-(15.5+32*side);v=y-7.5
            if abs(u)>14.6:continue
            curve=math.sqrt(max(0,1-(u/14.6)**2))
            slant=(u if side==0 else -u)*.10
            top=(-7.4*curve+slant)*open_amount;bottom=7.4*curve*open_amount
            if v<top-.15 or v>bottom+.15:continue
            if mode==0:
                rgb=mix(sharingan(u,v,rotation),mangekyo(u,v,rotation),change)
            elif side==0:
                rgb=mangekyo(u,v,math.pi/6)
            else:
                r=math.hypot(u,v)
                reveal=ease((change*7.8-r)/1.3)
                rgb=mix(mangekyo(u,v,math.pi/6),rinnegan(u,v),reveal)
            if min(abs(v-top),abs(v-bottom))<.55:
                rgb=COLORS[8] if mode==1 and side==1 and change>.65 else COLORS[3]
            if open_amount<.15:rgb=COLORS[3]
            index=min(range(16),key=lambda i:sum((rgb[c]-COLORS[i][c])**2 for c in range(3)))
            im.putpixel((x,y),index)
    return im


def main():
    targets=[ROOT/'android/app/src/main/assets/eyes',ROOT/'ios/Resources/Eyes']
    for target in targets:target.mkdir(parents=True,exist_ok=True)
    for mode,name in enumerate(NAMES):
        images=[frame(mode,n) for n in range(FRAMES)]
        out=targets[0]/f'{name}.gif'
        images[0].save(out,save_all=True,append_images=images[1:],duration=DELAY,loop=0,
                       optimize=False,disposal=1,palette=images[0].getpalette())
        data=out.read_bytes();assert len(data)<=8192,(name,len(data))
        for target in targets[1:]:(target/out.name).write_bytes(data)
        print(name,len(data))

if __name__=='__main__':main()
