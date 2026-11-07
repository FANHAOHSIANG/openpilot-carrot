"""Validate decoder assets, palette structure, geometry and identical platform fixtures."""
from pathlib import Path
from PIL import Image
from io import BytesIO
root=Path(__file__).resolve().parents[1]
for name in ['crystal','gaze','devil','spiral','flame','mecha']:
 b=(root/f'ios/Resources/Eyes/{name}.gif').read_bytes()
 assert b==(root/f'android/app/src/main/assets/eyes/{name}.gif').read_bytes()
 assert 61<=len(b)<=8192 and b[10]&0x87==0x83
 im=Image.open(BytesIO(b));assert im.size==(64,16) and im.info['loop']==0
 duration=0;distinct=set()
 for i in range(im.n_frames):
  im.seek(i);duration+=im.info['duration'];distinct.add(im.convert('RGB').tobytes())
 assert duration==1600 and len(distinct)>=4,(name,duration,len(distinct))
 # The entire GIF must use its one tintable global palette, with no local overrides.
 p=61;frames=0
 def skip_blocks(p):
  while b[p]:p+=1+b[p]
  return p+1
 while p<len(b):
  marker=b[p];p+=1
  if marker==0x3b:break
  if marker==0x21:p=skip_blocks(p+1)
  elif marker==0x2c:
   assert not b[p+8]&128,(name,'local palette')
   p=skip_blocks(p+10);frames+=1
  else:raise AssertionError((name,p,marker))
 assert frames==im.n_frames
 print(name, len(b), 'bytes',frames,'encoded frames / 32 logical frames / 1.6s')
for name in ['vehicle_scenarios.csv','gif_vectors.csv']:
 assert (root/'ios/tests'/name).read_bytes()==(root/'android/tests'/name).read_bytes()
print('Asset decoding, palette layout and shared fixtures passed')
