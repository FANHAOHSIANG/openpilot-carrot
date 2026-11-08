package tw.carrot.led;
public final class VehicleNotificationTests {
  static void check(String got,String want) { if(!got.equals(want)) throw new AssertionError(got+" != "+want); }
  public static void main(String[] args) {
    VehicleNotificationPolicy p=new VehicleNotificationPolicy();
    check(p.next("brake",true,0),"brake");
    check(p.next("brake",true,5000),"");
    check(p.next("left",true,5100),"left");
    check(p.next("right",true,5200),"");
    check(p.next("brake",true,8100),"brake");
    check(p.next("left",false,12000),"");
    check(p.next("right",true,12001),"right");
    check(p.next("",true,16000),"");
    check(p.next("right",true,16001),"right");
    System.out.println("Vehicle notification: 9 checks passed");
  }
}
