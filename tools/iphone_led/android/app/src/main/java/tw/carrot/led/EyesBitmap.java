package tw.carrot.led;

/** Original pixel eyes, shared geometry with the iOS renderer. */
final class EyesBitmap {
  static byte[] make(int width,int height,int variant,long phase) {
    if(width<1 ||height<1 ||width>256 ||height>64) return new byte[0];
    int stride=(width+7)/8;byte[] bits=new byte[stride*height];
    long tick=Math.max(0,phase);boolean blink=tick%18==16;
    int look=variant==1?new int[]{0,0,-3,-3,0,3,3,0}[(int)((tick/2)%8)]:0;
    for(int y=0;y<height;y++) for(int x=0;x<width;x++) {
      double px=x*64.0/width,py=y*16.0/height;int side=px<32?0:1;
      double u=px-(side==0?16:48),v=py-8;if(Math.abs(u)>=14) continue;
      double curve=5*Math.pow(Math.max(0,1-Math.abs(u)/14),.6);
      boolean inside=Math.abs(v)<=curve;
      if(variant==2) inside=inside&&v>=-3+.22*(side==0?u:-u);
      if(blink) inside=Math.abs(v)<1&&Math.abs(u)<12;
      boolean pupil=Math.pow((u-look)/2.5,2)+Math.pow(v/3.5,2)<1;
      boolean highlight=Math.abs(u-look+1)<1.2&&Math.abs(v+2)<1;
      if(inside&&(blink||!pupil||highlight))bits[y*stride+x/8]|=(byte)(128>>(x%8));
    }
    return bits;
  }
}
