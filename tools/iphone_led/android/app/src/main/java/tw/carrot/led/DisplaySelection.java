package tw.carrot.led;

/** Select the output without altering the ongoing vehicle state during a manual preview. */
final class DisplaySelection {
  static String choose(
      boolean automatic,
      boolean fresh,
      String vehicle,
      int slot,
      String preview,
      long deadline,
      long now) {
    if (!preview.isEmpty() && now < deadline) return preview;
    if (automatic && !fresh) return "";
    if (automatic && !vehicle.isEmpty()) return vehicle;
    return slot == 5 ? "eyes" : slot >= 0 && slot < 5 ? "slot" + slot : "";
  }
}
