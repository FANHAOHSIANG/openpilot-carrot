package tw.carrot.led;
/** Longest matching IPv4 route wins; default routes never identify the C4 LAN. */
public final class LanRoute {
  public static int match(String host, String network, int prefix) {
    if (prefix < 1 || prefix > 32) return -1;
    try {
      long h=ipv4(host), n=ipv4(network), mask=(0xffffffffL << (32-prefix)) & 0xffffffffL;
      return (h & mask)==(n & mask) ? prefix : -1;
    } catch (IllegalArgumentException e) { return -1; }
  }
  private static long ipv4(String text) {
    String[] parts=text.split("\\.",-1); if(parts.length!=4) throw new IllegalArgumentException();
    long result=0;
    for(String p:parts) { if(!p.matches("[0-9]{1,3}")) throw new IllegalArgumentException(); int n=Integer.parseInt(p); if(n>255) throw new IllegalArgumentException(); result=(result<<8)|n; }
    return result;
  }
}
