package tw.carrot.led;

/** One-shot opening animation. A vehicle event or manual action cancels it. */
final class StartupPlayback {
  static final int NONE = -1, WAIT = -2, NATIVE = -3, DURATION_MS = 2400;
  boolean active;
  private long requested, started = -1;
  private boolean awaitingDelivery;
  private int lastFrame = -1;

  void begin(long now) { active=true; requested=now; started=-1; awaitingDelivery=false; lastFrame=-1; }
  void cancel() { active=false; awaitingDelivery=false; }

  int step(long now, boolean ready, boolean power, boolean interrupt, boolean idle, boolean nativeMode) {
    if (!active) return NONE;
    if (!ready || !power || interrupt || now < requested || now-requested >= 12000) {
      cancel(); return NONE;
    }
    if (awaitingDelivery) {
      if (!idle) return WAIT;
      awaitingDelivery=false; started=now;
    }
    if (started < 0) {
      if (!idle) return WAIT;
      started=now;
      if (nativeMode) { awaitingDelivery=true; return NATIVE; }
    }
    long elapsed=now-started;
    if (elapsed >= DURATION_MS) { cancel(); return NONE; }
    if (nativeMode || !idle) return WAIT;
    int frame=(int)(elapsed/200)*4;
    if (frame == lastFrame) return WAIT;
    lastFrame=frame; return frame;
  }
}
