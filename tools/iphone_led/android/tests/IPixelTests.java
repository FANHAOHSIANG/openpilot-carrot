package tw.carrot.led;
import java.util.*;
public final class IPixelTests {
 static void check(boolean ok,String message) { if(!ok) throw new AssertionError(message); }
 public static void main(String[] args) throws Exception {
  // Golden frames from pypixelcolor 7ff1f5c build_text_properties/build_text_send_plan,
  // encode_character_block and bit reversal; asymmetric pixels catch transposition.
  String[] expected = {"450000010036000000c936cd7b00000200010100500012abef010000000012abef0153287a154f3c610b5826751f42316b0012abefa5f79cc1b3e886d5affc91cbb8e68ddf","4500000100360000003f42ab8200000200010105500012abef010000000012abef0153287a154f3c610b5826751f42316b0012abefa5f79cc1b3e886d5affc91cbb8e68ddf","450000010036000000382ffcff00000200010101500012abef010000000012abef0153287a154f3c610b5826751f42316b0012abefa5f79cc1b3e886d5affc91cbb8e68ddf","4500000100360000007df5119b00000200010102500012abef010000000012abefa5f79cc1b3e886d5affc91cbb8e68ddf0012abef0153287a154f3c610b5826751f42316b","4500000100360000006d6e89d500000200010106500012abef010000000012abef0153287a154f3c610b5826751f42316b0012abefa5f79cc1b3e886d5affc91cbb8e68ddf","45000001003600000015da7c4600000200010100500112abef010000000012abef0153287a154f3c610b5826751f42316b0012abefa5f79cc1b3e886d5affc91cbb8e68ddf"};
  byte[] bitmap=new byte[32]; for(int i=0;i<32;i++) bitmap[i]=(byte)(i*37+128);
  for(int e=0;e<6;e++) check(Arrays.equals(IPixelProtocol.text(bitmap,16,16,0x12abef,e),HexFormat.of().parseHex(expected[e])),"reference frame effect "+e);
  byte[] clear=IPixelProtocol.text(new byte[128],64,16,0,0);
  check(clear.length==189 && clear[14]==0 && clear[15]==8,"transient blank screen, 8 blocks");
  for(int i=29;i<clear.length;i++) check(clear[i]==0,"clear leaves no lit pixel or color");
  check(Arrays.equals(IPixelProtocol.power(false),new byte[]{5,0,7,1,0}),"power off");
  check(IPixelProtocol.ack(new byte[]{5,0,0,1,3}) && !IPixelProtocol.ack(new byte[]{5,0,0,1,2}) && !IPixelProtocol.ack(new byte[0]),"ACK validation");
  check(IPixelProtocol.text(new byte[4080],2040,16,0,0).length==5129,"max frame stays in one 12KB window");
  int rejected=0;
  for(int[] size:new int[][]{{64,32},{2041,16},{0,16},{64,16}}) try {IPixelProtocol.text(new byte[0],size[0],size[1],0,0);} catch(IllegalArgumentException ex){rejected++;}
  check(rejected==4,"invalid geometry rejected");
  for(String row:java.nio.file.Files.readAllLines(java.nio.file.Path.of("tests/gif_vectors.csv"))){
   String[] v=row.split(",");byte[] gif=java.nio.file.Files.readAllBytes(java.nio.file.Path.of("app/src/main/assets/eyes/"+v[0]));
   byte[] packet=IPixelProtocol.gif(gif);
   check(HexFormat.of().formatHex(Arrays.copyOf(packet,15)).equals(v[1]),"upstream GIF header "+v[0]);
   check(HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(packet)).equals(v[2]),"upstream GIF payload "+v[0]);
  }
  int bad=0;for(byte[] gif:new byte[][]{new byte[0],new byte[9000],new byte[64]})try{IPixelProtocol.gif(gif);}catch(IllegalArgumentException ex){bad++;}
  check(bad==3,"GIF bounds/signature rejected");
  System.out.println("iPixel: 6 upstream golden frames, clear/power/ACK/bounds checks passed");
 }
}
