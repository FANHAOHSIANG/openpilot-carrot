package tw.carrot.led;
import android.content.Context;
import android.graphics.*;
import java.io.*;
import java.util.*;

/** Original GIFs with one 16-color global palette; tinting never changes compressed indices. */
final class EyeAnimations {
  static final String[] FILES={"crystal","gaze","devil","spiral","flame","mecha"};
  static final String[] NAMES={"晶亮眨眼","靈動眼","惡魔眼","螺旋眼","火焰眼","機甲眼"};
  static int index(int n){return Math.max(0,Math.min(FILES.length-1,n));}
  static final Map<String,byte[]> cache=new HashMap<>();
  static synchronized byte[] gif(Context context,int variant,int color){
    variant=index(variant);String key=variant+":"+(color&0xffffff);
    if(cache.containsKey(key))return cache.get(key);
    try(InputStream in=context.getAssets().open("eyes/"+FILES[variant]+".gif")){
      ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] block=new byte[4096];int n;
      while((n=in.read(block))!=-1)out.write(block,0,n);
      byte[] data=out.toByteArray();
      if(data.length<61 || data.length>8192 || (data[10]&0x87)!=0x83)throw new IOException("invalid eyes palette");
      for(int i=0;i<16;i++)for(int channel=0;channel<3;channel++){
        int base=(color>>(16-8*channel))&255;
        int value=i<=10?(base*i/10):(base+(255-base)*(i-10)/5);
        data[13+i*3+channel]=(byte)value;
      }
      if(cache.size()>=24)cache.clear();cache.put(key,data);return data;
    }catch(IOException e){return null;}
  }
  static Movie movie(Context context,int variant,int color){byte[] b=gif(context,variant,color);return b==null?null:Movie.decodeByteArray(b,0,b.length);}
  static Bitmap raster(Context context,int variant,int color,int width,int height,long time){
    Movie movie=movie(context,variant,color);if(movie==null)return null;
    Bitmap bitmap=Bitmap.createBitmap(width,height,Bitmap.Config.ARGB_8888);
    Canvas canvas=new Canvas(bitmap);canvas.drawColor(Color.BLACK);canvas.scale(width/64f,height/16f);
    movie.setTime((int)(time%Math.max(1,movie.duration())));movie.draw(canvas,0,0);return bitmap;
  }
}
