package tw.carrot.led;
public class LanRouteTests {
 public static void main(String[] args) {
  if(LanRoute.match("192.168.50.2","192.168.50.0",24)!=24) throw new AssertionError();
  if(LanRoute.match("192.168.50.2","192.168.60.0",24)!=-1) throw new AssertionError();
  if(LanRoute.match("192.168.50.2","0.0.0.0",0)!=-1) throw new AssertionError();
  if(LanRoute.match("192.168.50.2","192.168.0.0",16)!=16) throw new AssertionError();
  if(LanRoute.match("192.168.50.2","::",64)!=-1) throw new AssertionError();
  if(LanRoute.match("999.1.1.1","0.0.0.0",8)!=-1) throw new AssertionError();
  System.out.println("LAN route: 6 checks passed");
 }
}
