package tw.carrot.led;
import java.nio.file.*;
import java.util.*;

public final class StartupTests {
  public static void main(String[] args) throws Exception {
    StartupPlayback p=new StartupPlayback(); int checks=0;
    for(String line:Files.readAllLines(Path.of("tests/startup_scenarios.csv"))){
      String[] c=line.split(","); if(c[0].equals("action"))continue;
      long now=Long.parseLong(c[1]);int result=-1;
      if(c[0].equals("begin"))p.begin(now);
      else if(c[0].equals("cancel"))p.cancel();
      else result=p.step(now,c[2].equals("1"),c[3].equals("1"),c[4].equals("1"),c[5].equals("1"),c[6].equals("1"));
      if(result!=Integer.parseInt(c[7]) || p.active!=c[8].equals("1"))throw new AssertionError(line+" got "+result+"/"+p.active);
      checks++;
    }
    p.begin(0);
    if(p.step(0,true,true,false,true,false,200)!=0 || p.step(50,true,true,false,true,false,200)!=-2 || p.step(200,true,true,false,true,false,200)!=4)throw new AssertionError("iPixel compatibility cadence");
    byte[] gif=Files.readAllBytes(Path.of("app/src/main/assets/startup/startup_car.gif"));
    byte[] packet=IPixelProtocol.gif(gif);
    String[] golden=Files.readString(Path.of("tests/startup_gif.csv")).trim().split(",");
    if(!HexFormat.of().formatHex(Arrays.copyOf(packet,15)).equals(golden[0]) ||
       !HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(packet)).equals(golden[1]))throw new AssertionError("startup GIF upstream packet");
    // LOY still frames its 96x16 canvas in the original FFF2 protocol.
    byte[] bits=new byte[192];Arrays.fill(bits,(byte)255);
    List<byte[]> pixels=LoyProtocol.pixels(bits,96,16,0xff7e00);
    if(pixels.size()!=1 || pixels.get(0).length!=207)throw new AssertionError("LOY 96x16 pixel geometry");
    byte[] framed=new LoyProtocol().frame(pixels.get(0));
    if((framed[0]&255)!=0xaa || (framed[1]&255)!=0x55)throw new AssertionError("LOY envelope retained");
    System.out.println(checks+" shared startup transitions, upstream GIF and LOY geometry passed");
  }
}
