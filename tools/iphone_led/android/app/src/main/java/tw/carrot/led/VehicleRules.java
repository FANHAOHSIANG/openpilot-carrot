package tw.carrot.led;

/** Uses monotonic milliseconds; no Android dependencies. */
public final class VehicleRules {
  private long slowingSince = -1, hardSince = -1, trafficSince = -1;
  private boolean slowing, hard;

  public void reset() {
    slowingSince = hardSince = trafficSince = -1;
    slowing = hard = false;
  }

  public String choose(
      double speed,
      double accel,
      boolean brake,
      boolean left,
      boolean right,
      String gear,
      long now) {
    if (!Double.isFinite(speed) || !Double.isFinite(accel)) {
      reset();
      return "";
    }
    if (slowing) {
      if (speed < 3 / 3.6 || accel >= -0.25) {
        slowing = false;
        slowingSince = -1;
      }
    } else if (speed >= 5 / 3.6 && accel <= -0.5) {
      if (slowingSince < 0) slowingSince = now;
      if (now - slowingSince >= 300) slowing = true;
    } else slowingSince = -1;
    if (hard) {
      if (speed < 3 / 3.6 || accel >= -1.5) {
        hard = false;
        hardSince = -1;
      }
    } else if (speed >= 5 / 3.6 && accel <= -2) {
      if (hardSince < 0) hardSince = now;
      if (now - hardSince >= 300) hard = true;
    } else hardSince = -1;
    boolean drive = gear.equals("drive") || gear.equals("d");
    if (drive && (brake || slowing)) {
      if (left && right) {
        if (hard && trafficSince < 0) trafficSince = now;
        if (trafficSince >= 0) return ((now - trafficSince) / 2000) % 2 == 0 ? "減速中" : "前方塞車";
      } else trafficSince = -1;
      return "減速中";
    }
    trafficSince = -1;
    if (gear.equals("reverse") || gear.equals("r")) {
      reset();
      return "倒車";
    }
    if (left && right) {
      if (gear.equals("park") || gear.equals("p")) return "暫停一下謝謝";
      return drive ? "謝謝" : "";
    }
    return left ? "左轉彎" : right ? "右轉彎" : "";
  }
}
