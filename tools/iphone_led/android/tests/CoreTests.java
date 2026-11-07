package tw.carrot.led;

import java.util.*;

public class CoreTests {
  static int checks;

  static void eq(Object actual, Object expected) {
    checks++;
    if (!Objects.equals(actual, expected))
      throw new AssertionError("expected " + expected + " got " + actual);
  }

  static String hex(byte[] a) {
    StringBuilder b = new StringBuilder();
    for (byte v : a) b.append(String.format("%02x", v & 255));
    return b.toString();
  }

  public static void main(String[] args) {
    eq(DisplaySelection.choose(true, true, "減速中", 1, "左轉彎", 5000, 4999), "左轉彎");
    eq(DisplaySelection.choose(true, true, "減速中", 1, "左轉彎", 5000, 5000), "減速中");
    eq(DisplaySelection.choose(true, false, "減速中", 1, "", 0, 5000), "");
    eq(DisplaySelection.choose(false, false, "減速中", 1, "", 0, 5000), "slot1");
    eq(DisplaySelection.choose(true, true, "", 1, "", 0, 5000), "slot1");
    eq(DisplaySelection.choose(false, true, "減速中", -1, "", 0, 5000), "");
    eq(DisplaySelection.choose(false, false, "", -1, "倒車", 5000, 0), "倒車");
    eq(DisplaySelection.choose(false, false, "", -1, "倒車", 5000, 5000), "");
    eq(DisplaySelection.choose(true,true,"減速中",5,"",0,5000),"減速中");
    eq(DisplaySelection.choose(true,true,"",5,"",0,5000),"eyes");
    eq(DisplaySelection.choose(true,false,"",5,"",0,5000),"");
    eq(DisplaySelection.choose(false,false,"",5,"",0,5000),"eyes");
    eq(DisplaySelection.choose(false,false,"",-1,"",0,5000),"");
    VehicleRules r = new VehicleRules();
    eq(r.choose(10, 0, false, true, false, "drive", 0), "左轉彎");
    eq(r.choose(10, -.1, true, true, false, "drive", 100), "減速中");
    eq(r.choose(10, 0, false, true, false, "drive", 200), "左轉彎");
    eq(r.choose(10, -.6, false, false, true, "drive", 300), "右轉彎");
    eq(r.choose(10, -.6, false, false, true, "drive", 599), "右轉彎");
    eq(r.choose(10, -.6, false, false, true, "drive", 600), "減速中");
    eq(r.choose(10, -.3, false, false, true, "drive", 700), "減速中");
    eq(r.choose(10, -.2, false, false, true, "drive", 800), "右轉彎");
    eq(r.choose(0, 0, true, true, true, "park", 900), "暫停一下謝謝");
    eq(r.choose(5, 0, false, true, true, "drive", 1000), "謝謝");
    eq(r.choose(1, -1, true, true, true, "reverse", 1100), "倒車");
    r.reset();
    eq(r.choose(10, -3, true, true, true, "drive", 2000), "減速中");
    eq(r.choose(10, -3, true, true, true, "drive", 2300), "減速中");
    eq(r.choose(10, -.6, true, true, true, "drive", 4299), "減速中");
    eq(r.choose(10, -.6, true, true, true, "drive", 4300), "減速中");
    eq(r.choose(10, -.6, true, true, true, "drive", 6300), "減速中");
    eq(r.choose(10, -.6, true, false, true, "drive", 6400), "減速中");
    r.reset();
    eq(r.choose(10, 0, false, true, true, "drive", 6500), "謝謝");
    eq(r.choose(Double.NaN, 0, false, true, true, "drive", 6600), "");
    eq(r.choose(0, 0, false, false, false, "park", 6700), "");
    LoyProtocol p = new LoyProtocol();
    eq(hex(p.frame(new byte[] {4, 2, 0, 1})), "aa55ffff0a000100c10204020001d203");
    eq(hex(LoyProtocol.clear(96, 16)), "320d0100000000000000005f000f00");
    byte[] bits = new byte[192];
    bits[0] = (byte) 0x80;
    bits[191] = 1;
    List<byte[]> pixels = LoyProtocol.pixels(bits, 96, 16, 0xffb400);
    eq(pixels.size(), 1);
    byte[] data = pixels.get(0);
    eq(data[0] & 255, 0x32);
    eq(data[1] & 255, 0x81);
    eq(data[2] & 255, 204);
    eq(data[15] & 255, 128);
    eq(data[data.length - 1] & 255, 1);
    byte[] large = new byte[2048];
    eq(LoyProtocol.pixels(large, 256, 64, 0).size(), 10);
    System.out.println(checks + " core checks passed");
  }
}
