package tw.carrot.led;
import java.util.*;
public final class EyesTests {
  static void check(boolean ok){if(!ok)throw new AssertionError("Eyes geometry regression");}
  static int count(byte[] b){int n=0;for(byte v:b)n+=Integer.bitCount(v&255);return n;}
  public static void main(String[] args){
    for(int w:new int[]{64,96,97})for(int mode=0;mode<3;mode++){
      byte[] open=EyesBitmap.make(w,16,mode,0),blink=EyesBitmap.make(w,16,mode,16);
      check(open.length==((w+7)/8)*16);check(count(open)>count(blink)&&count(blink)>0);
      if(w%8!=0)for(int y=0;y<16;y++)check((open[(y+1)*((w+7)/8)-1]&0x7f)==0);
    }
    check(!Arrays.equals(EyesBitmap.make(64,16,1,0),EyesBitmap.make(64,16,1,4)));
    check(EyesBitmap.make(0,16,0,0).length==0);
    System.out.println("Eyes: dimensions, blink, gaze, and partial-byte bounds passed");
  }
}
