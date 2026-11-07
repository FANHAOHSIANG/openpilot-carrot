"""Original 64x16 indexed eye animations. Requires Pillow. No vendor images."""
from pathlib import Path
import math
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
NAMES=['crystal','gaze','devil','spiral','flame','mecha']
FRAMES=32
DELAY=50
palette=[v for i in range(16) for v in (i*17,)*3]

def frame(mode,n):
    t=n/FRAMES
    # A continuous close/open movement over six frames near the end of the loop.
    close=max(0,1-abs(n-(FRAMES-7))/3)
    opening=max(.02,1-close)
    look=3.5*math.sin(2*math.pi*t) if mode==1 else 0
    im=Image.new('P',(64,16));im.putpalette(palette)
    for y in range(16):
      for x in range(64):
        side=0 if x<32 else 1
        u=x-(15.5+32*side);v=y-7.5
        if abs(u)>=14.5:continue
        curve=math.sqrt(max(0,1-(u/14.5)**2))
        slant=(u if side==0 else -u)*(.15 if mode>=2 else .08)
        top=(-5.9*curve+slant)*opening;bottom=(5.9*curve)*opening
        if v<top-.2 or v>bottom+.2:continue
        edge=min(abs(v-top),abs(v-bottom))
        dx=u-look;r=math.sqrt((dx/5.7)**2+(v/5.7)**2)
        angle=math.atan2(v,dx)
        idx=2
        if edge<.7:idx=8
        elif r<1:
          idx=int(4+5*(1-r)+1.3*math.cos(angle*10+r*8))
          if mode==3:idx=int(5+4*math.sin(r*19+angle*2-t*math.pi*4))
          if mode==5:idx=10 if .60<r<.82 or abs(v)<.5 else 4
          if (dx/2.2)**2+(v/3.5)**2<1:idx=0
          if abs(dx+1.5)<1.3 and abs(v+2.4)<.9:idx=15
        if mode==2 and edge<1.1:idx=10
        if mode==4:
          if edge<1.8:idx=int(7+3*math.sin(u*.9+t*math.pi*4))
          elif r<1 and idx>0:idx=min(12,idx+2)
        if opening<.15:idx=9
        im.putpixel((x,y),max(0,min(15,idx)))
    return im

def main():
    targets=[ROOT/'android/app/src/main/assets/eyes',ROOT/'ios/Resources/Eyes']
    for p in targets:p.mkdir(parents=True,exist_ok=True)
    for mode,name in enumerate(NAMES):
      images=[frame(mode,n) for n in range(FRAMES)]
      output=targets[0]/f'{name}.gif'
      images[0].save(output,save_all=True,append_images=images[1:],duration=DELAY,loop=0,optimize=False,disposal=1,palette=images[0].getpalette())
      data=output.read_bytes()
      assert len(data)<=8192,(name,len(data))
      for target in targets[1:]: (target/output.name).write_bytes(data)
      print(name,len(data))
if __name__=='__main__':main()
