package tw.carrot.led;

import java.io.ByteArrayOutputStream;
import java.util.*;

public final class LoyProtocol {
  private int sequence = 1;

  public byte[] frame(byte[] payload) {
    ByteArrayOutputStream b = new ByteArrayOutputStream();
    add(b, 0xaa, 0x55, 0xff, 0xff);
    word(b, payload.length + 6);
    word(b, sequence++ & 65535);
    add(b, 0xc1, 2);
    b.write(payload, 0, payload.length);
    int sum = 0;
    for (byte v : b.toByteArray()) sum += v & 255;
    word(b, sum & 65535);
    return b.toByteArray();
  }

  public static void add(ByteArrayOutputStream b, int... a) {
    for (int v : a) b.write(v);
  }

  public static void word(ByteArrayOutputStream b, int n) {
    add(b, n & 255, (n >> 8) & 255);
  }

  public static byte[] draw(byte[] data) {
    ByteArrayOutputStream b = new ByteArrayOutputStream();
    b.write(0x32);
    if (data.length < 128) b.write(data.length);
    else if (data.length < 256) add(b, 0x81, data.length);
    else {
      b.write(0x82);
      word(b, data.length);
    }
    b.write(data, 0, data.length);
    return b.toByteArray();
  }

  public static byte[] clear(int w, int h) {
    ByteArrayOutputStream b = new ByteArrayOutputStream();
    add(b, 1, 0, 0, 0, 0);
    word(b, 0);
    word(b, 0);
    word(b, w - 1);
    word(b, h - 1);
    return draw(b.toByteArray());
  }

  public static List<byte[]> pixels(byte[] packed, int w, int h, int color) {
    return pixels(packed, w, h, color, false);
  }

  // Animation frames are cleared first. Omit transparent rows and empty layers;
  // retain the existing full-width bitmap command and its original coordinates.
  public static List<byte[]> animationPixels(byte[] packed, int w, int h, int color) {
    return pixels(packed, w, h, color, true);
  }

  private static List<byte[]> pixels(byte[] packed, int w, int h, int color, boolean compact) {
    if (w <= 0 || w > 256 || h <= 0 || h > 64) throw new IllegalArgumentException("bitmap size");
    int row = (w + 7) / 8, step = Math.max(1, 240 / row);
    List<byte[]> out = new ArrayList<>();
    if (packed.length != row * h) throw new IllegalArgumentException("bitmap size");
    int first = 0, last = h;
    if (compact) {
      while (first < last && emptyRow(packed, first, row)) first++;
      while (last > first && emptyRow(packed, last - 1, row)) last--;
    }
    for (int y = first; y < last; y += step) {
      int end = Math.min(last, y + step);
      ByteArrayOutputStream b = new ByteArrayOutputStream();
      add(b, 0, (color >> 16) & 255, (color >> 8) & 255, color & 255);
      word(b, 0);
      word(b, y);
      word(b, w - 1);
      word(b, end - 1);
      b.write(packed, y * row, (end - y) * row);
      out.add(draw(b.toByteArray()));
    }
    return out;
  }

  private static boolean emptyRow(byte[] data, int y, int stride) {
    for (int i = y * stride; i < (y + 1) * stride; i++) if (data[i] != 0) return false;
    return true;
  }
}
