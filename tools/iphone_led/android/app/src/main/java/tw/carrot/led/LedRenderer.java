package tw.carrot.led;

import android.graphics.*;
import java.util.*;

final class LedRenderer {
  private static Typeface imported;
  private static long importedStamp = -1;

  static List<byte[]> render(Settings settings, Settings.Style style, long tick) {
    int w = settings.width(), h = settings.height(), fh = settings.fontHeight();
    List<byte[]> commands = new ArrayList<>();
    commands.add(new byte[] {0x30, 1, (byte) 0x90});
    commands.add(LoyProtocol.clear(w, h));
    if (style == null || style.text.isEmpty() || (style.effect == 1 && tick % 2 == 1))
      return commands;
    Paint p = new Paint();
    p.setColor(Color.WHITE);
    p.setTextSize(64);
    p.setAntiAlias(false);
    String[] families = {"sans-serif", "serif", "monospace", "sans-serif-rounded"};
    p.setTypeface(
        Typeface.create(
            families[Math.max(0, Math.min(3, style.font))],
            style.bold ? Typeface.BOLD : Typeface.NORMAL));
    if (style.font == 4 && settings.fontFile.exists()) {
      try {
        long stamp = settings.fontFile.lastModified();
        if (imported == null || stamp != importedStamp) {
          imported = Typeface.createFromFile(settings.fontFile);
          importedStamp = stamp;
        }
        p.setTypeface(Typeface.create(imported, style.bold ? Typeface.BOLD : Typeface.NORMAL));
      } catch (Exception ignored) {
      }
    }
    Rect bounds = new Rect();
    p.getTextBounds(style.text, 0, style.text.length(), bounds);
    if (bounds.height() == 0) return commands;
    float scale = (float) fh / bounds.height();
    float sx = scale * settings.fontWidth() / 100f;
    float advance = p.measureText(style.text);
    float natural = Math.max(advance, bounds.right) - Math.min(0, bounds.left);
    boolean scrolling = style.effect == 2 || style.effect == 3;
    if (!scrolling && natural * sx > w) sx = w / natural;
    int tw = Math.max(1, (int) Math.ceil(natural * sx));
    Bitmap bitmap = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
    Canvas c = new Canvas(bitmap);
    c.drawColor(Color.BLACK);
    float y = (h - fh) / 2f;
    if (scrolling) {
      int span = tw + w;
      int progress = (int) ((tick * 2) % span);
      float x = style.effect == 2 ? w - progress : progress - tw;
      c.save();
      c.translate(x, y);
      c.scale(sx, scale);
      c.drawText(style.text, -Math.min(0, bounds.left), -bounds.top, p);
      c.restore();
    } else {
      c.translate((w - tw) / 2f, y);
      c.scale(sx, scale);
      c.drawText(style.text, -Math.min(0, bounds.left), -bounds.top, p);
    }
    byte[] bits = new byte[((w + 7) / 8) * h];
    for (int yy = 0; yy < h; yy++)
      for (int x = 0; x < w; x++)
        if (Color.red(bitmap.getPixel(x, yy)) > 60)
          bits[yy * ((w + 7) / 8) + x / 8] |= (byte) (128 >> (x % 8));
    bitmap.recycle();
    int color = style.color;
    if (style.effect == 4) {
      double[] levels = {.25, .4, .6, .8, 1, .8, .6, .4};
      double n = levels[(int) (tick % 8)];
      color =
          Color.rgb(
              (int) (Color.red(color) * n),
              (int) (Color.green(color) * n),
              (int) (Color.blue(color) * n));
    }
    if (style.effect == 5) color = Color.HSVToColor(new float[] {(tick % 12) * 30, 1, 1});
    commands.addAll(LoyProtocol.pixels(bits, w, h, color));
    return commands;
  }
}
