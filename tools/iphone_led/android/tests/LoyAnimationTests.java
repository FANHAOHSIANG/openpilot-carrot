package tw.carrot.led;
import java.nio.file.*;
import java.util.*;

public final class LoyAnimationTests {
  static int checks;
  static void check(boolean v, String message) { if (!v) throw new AssertionError(message); checks++; }
  static int word(byte[] a,int i){return (a[i]&255)|((a[i+1]&255)<<8);}
  static void roundTrip(byte[] bits,int w,int h) {
    byte[] rendered=new byte[bits.length];int stride=(w+7)/8;
    for(byte[] cmd:LoyProtocol.animationPixels(bits,w,h,0x123456)){
      check((cmd[0]&255)==0x32,"draw opcode");int n=cmd[1]&255, start=2;
      if(n==0x81){n=cmd[2]&255;start=3;}else if(n==0x82){n=word(cmd,2);start=4;}
      check(cmd.length==start+n && n<=252,"bounded complete command");
      check(cmd[start]==0 && (cmd[start+1]&255)==0x12 && (cmd[start+2]&255)==0x34 && (cmd[start+3]&255)==0x56,"color preserved");
      int x0=word(cmd,start+4),y0=word(cmd,start+6),x1=word(cmd,start+8),y1=word(cmd,start+10);
      check(x0==0 && x1==w-1 && y0>=0 && y1>=y0 && y1<h,"original coordinates");
      check(n-12==(y1-y0+1)*stride,"row alignment");
      System.arraycopy(cmd,start+12,rendered,y0*stride,n-12);
      byte[] frame=new LoyProtocol().frame(cmd);int sum=0;for(int i=0;i<frame.length-2;i++)sum+=frame[i]&255;
      check(word(frame,frame.length-2)==(sum&65535),"checksum");
    }
    check(Arrays.equals(bits,rendered),"compact screen differs from full canvas");
  }
  public static void main(String[] args)throws Exception {
    for(int w:new int[]{8,64,96,97,256})for(int h:new int[]{8,16,64}){
      int stride=(w+7)/8;byte[] bits=new byte[stride*h];roundTrip(bits,w,h);
      check(LoyProtocol.animationPixels(bits,w,h,0).isEmpty(),"empty layer must be omitted");
      for(int row:new int[]{0,h/2,h-1}){Arrays.fill(bits,(byte)0);bits[row*stride]=(byte)128;roundTrip(bits,w,h);}
      for(int i=0;i<bits.length;i++)bits[i]=(byte)((i*73+19)&255);roundTrip(bits,w,h);
    }
    byte[] band=new byte[192];Arrays.fill(band,4*12,12*12,(byte)255);roundTrip(band,96,16);
    int oldBytes=new LoyProtocol().frame(LoyProtocol.pixels(band,96,16,0).get(0)).length;
    int newBytes=new LoyProtocol().frame(LoyProtocol.animationPixels(band,96,16,0).get(0)).length;
    check(oldBytes==219 && newBytes==122,"96x16 cropped byte budget");
    for(int w:new int[]{64,96}){
      byte[] artwork=Files.readAllBytes(Path.of("app/src/main/assets/startup/startup"+w+".bin"));
      for(int frame=0;frame<48;frame++)for(int color=1;color<4;color++){
        byte[] layer=new byte[w/8*16];
        for(int y=0;y<16;y++)for(int x=0;x<w;x++)if(artwork[frame*w*16+y*w+x]==color)layer[y*(w/8)+x/8]|=(byte)(128>>(x%8));
        roundTrip(layer,w,16);
      }
    }
    System.out.println(checks+" LOY compact encoding, canvas equivalence, checksum and startup asset checks passed");
  }
}
