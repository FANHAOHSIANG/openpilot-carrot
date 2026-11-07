package tw.carrot.led;

import android.content.Context;
import java.io.*;
import java.util.*;

final class StartupArtwork {
  static final int[] COLORS = {0, 0xff7e00, 0x5de014, 0xffd300};
  private static final Map<Integer, byte[]> cache = new HashMap<>();
  static boolean supported(int w, int h) { return h == 16 && (w == 64 || w == 96); }
  static byte[] read(Context c, String name) {
    try (InputStream in=c.getAssets().open("startup/"+name); ByteArrayOutputStream out=new ByteArrayOutputStream()) {
      byte[] block=new byte[4096]; int n;
      while ((n=in.read(block)) != -1) { if(out.size()+n>100000)throw new IOException("asset too large"); out.write(block,0,n); }
      return out.toByteArray();
    } catch(IOException e) { throw new IllegalArgumentException("開屏素材缺失，請更新完整 App",e); }
  }
  static List<byte[]> commands(Settings s, int frame) {
    int w=s.width(), h=s.height();
    if(!supported(w,h))throw new IllegalArgumentException("unsupported startup size");
    if(frame==StartupPlayback.NATIVE)return Collections.singletonList(IPixelProtocol.gif(read(s.context,"startup_car.gif")));
    byte[] data=cache.get(w);
    if(data==null){data=read(s.context,"startup"+w+".bin");if(data.length!=w*16*48)throw new IllegalArgumentException("startup asset size");cache.put(w,data);}
    if(frame<0 || frame>=48)throw new IllegalArgumentException("startup frame");
    byte[][] layers=new byte[4][((w+7)/8)*16]; boolean[] used=new boolean[4];
    for(int y=0;y<16;y++)for(int x=0;x<w;x++){
      int color=data[frame*w*16+y*w+x]&255;
      if(color>=4)throw new IllegalArgumentException("startup color");
      if(color>0){used[color]=true;layers[color][y*((w+7)/8)+x/8]|=(byte)(128>>(x%8));}
    }
    List<byte[]> out=new ArrayList<>();
    if(s.ipixel()){
      byte[] merged=layers[1];for(int k=2;k<4;k++)for(int n=0;n<merged.length;n++)merged[n]|=layers[k][n];
      out.add(IPixelProtocol.text(merged,w,16,COLORS[1],0));
    }else{
      out.add(new byte[]{0x30,1,(byte)0x90});out.add(LoyProtocol.clear(w,16));
      for(int k=1;k<4;k++)if(used[k])out.addAll(LoyProtocol.pixels(layers[k],w,16,COLORS[k]));
    }
    return out;
  }
}
