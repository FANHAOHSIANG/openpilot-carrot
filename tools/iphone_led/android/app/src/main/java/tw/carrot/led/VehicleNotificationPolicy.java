package tw.carrot.led;
/** Only fresh real vehicle events; coalesce rapid changes to the latest event. */
public final class VehicleNotificationPolicy {
  private String last = "";
  private long lastAlert = -3000;
  public String next(String event, boolean eligible, long now) {
    if (!eligible || event.isEmpty()) { last = ""; return ""; }
    if (event.equals(last) || now - lastAlert < 3000) return "";
    last = event; lastAlert = now; return event;
  }
}
