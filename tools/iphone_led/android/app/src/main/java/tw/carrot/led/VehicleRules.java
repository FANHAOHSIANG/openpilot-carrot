package tw.carrot.led;

/** Display-only rules. Monotonic milliseconds, speed m/s and measured acceleration m/s². */
public final class VehicleRules {
  public static final double HARD_ACCEL=-4.5, HARD_MIN_SPEED=20.0/3.6;
  public static final long CONFIRM_MS=300, HOLD_MS=6000, MAX_GAP_MS=500;
  private long slowingSince=-1, hardSince=-1, releaseSince=-1, alertSince=-1, lastSample=-1;
  private int hardSamples;
  private boolean slowing, hard;
  public boolean emergencyActive;
  public void reset() {
    slowingSince=hardSince=releaseSince=alertSince=lastSample=-1;
    hardSamples=0;slowing=hard=emergencyActive=false;
  }
  private void resetEmergency(){hardSince=releaseSince=alertSince=-1;hardSamples=0;hard=emergencyActive=false;}
  public String choose(double speed,double accel,boolean brake,boolean left,boolean right,String gear,long now) {
    if(!Double.isFinite(speed)||!Double.isFinite(accel)||speed<0||now<0){reset();return "";}
    if(lastSample>=0 && (now<=lastSample || now-lastSample>MAX_GAP_MS))reset();
    lastSample=now;
    boolean drive="drive".equals(gear)||"d".equals(gear);
    if(!drive)resetEmergency();
    if(slowing){if(speed<3.0/3.6 || accel>=-.25){slowing=false;slowingSince=-1;}}
    else if(speed>=5.0/3.6 && accel<=-.5){if(slowingSince<0)slowingSince=now;if(now-slowingSince>=300)slowing=true;}
    else slowingSince=-1;
    if(drive){
      if(hard){
        if(accel> -2.0 || speed<3.0/3.6){
          if(releaseSince<0)releaseSince=now;
          if(now-releaseSince>=500){hard=false;hardSince=-1;hardSamples=0;}
        }else releaseSince=-1;
      }else if(speed>=HARD_MIN_SPEED && accel<=HARD_ACCEL){
        if(hardSince<0){hardSince=now;hardSamples=0;}
        hardSamples++;
        if(now-hardSince>=CONFIRM_MS && hardSamples>=3){hard=true;releaseSince=-1;alertSince=now;}
      }else{hardSince=-1;hardSamples=0;}
      emergencyActive=alertSince>=0 && (hard || now-alertSince<HOLD_MS);
      if(emergencyActive)return ((now-alertSince)/2000)%2==0?"前方塞車":"減速中";
      if(!hard)alertSince=-1;
    }
    if(drive && (brake||slowing))return "減速中";
    if("reverse".equals(gear)||"r".equals(gear)){reset();return "倒車";}
    if(left&&right){if("park".equals(gear)||"p".equals(gear))return "暫停一下謝謝";return drive?"謝謝":"";}
    return left?"左轉彎":right?"右轉彎":"";
  }
}
