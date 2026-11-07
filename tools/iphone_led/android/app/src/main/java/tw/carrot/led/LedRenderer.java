package tw.carrot.led;

import android.graphics.*;
import java.util.*;

final class LedRenderer {
  private static Typeface imported;
  private static long importedStamp = -1;

  static void pattern(Canvas c, Paint p, int effect, long tick, int w, int h) {
    c.save();
    c.scale(w / 96f, h / 16f);
    p.setStrokeWidth(1);
    p.setStyle(Paint.Style.STROKE);
    for (int center : new int[] {7, 88}) {
      if (effect == 6 || effect == 7) {
        int direction = effect == 6 ? -1 : 1;
        for (int offset : new int[] {-4, 3}) {
          float x = center + offset + direction * (tick % 4);
          Path path = new Path();
          path.moveTo(x - direction * 3, 3);
          path.lineTo(x, 8);
          path.lineTo(x - direction * 3, 13);
          c.drawPath(path, p);
        }
      } else if (effect == 8) {
        Path path = new Path();
        for (int x = 0; x < 14; x++) {
          float y = 8 + (float) Math.sin((x + tick * 2) * Math.PI / 6) * 3;
          if (x == 0) path.moveTo(center - 7 + x, y);
          else path.lineTo(center - 7 + x, y);
        }
        c.drawPath(path, p);
      } else if (effect == 9) {
        float size = tick % 4 < 2 ? 1 : .8f;
        c.save();
        c.translate(center, 8);
        c.scale(size, size);
        Path path = new Path();
        path.moveTo(0, 5);
        path.cubicTo(-12, -2, -4, -10, 0, -4);
        path.cubicTo(4, -10, 12, -2, 0, 5);
        c.drawPath(path, p);
        c.restore();
      } else if (effect == 10) {
        Path path = new Path();
        path.moveTo(center, 2);
        path.lineTo(center - 6, 13);
        path.lineTo(center + 6, 13);
        path.close();
        c.drawPath(path, p);
        if (tick % 2 == 0) {
          c.drawLine(center, 6, center, 9, p);
          c.drawPoint(center, 11, p);
        }
      }
    }
    c.restore();
    p.setStyle(Paint.Style.FILL);
  }

  static List<byte[]> render(Settings settings, Settings.Style style, long tick, boolean nativeEyes) {
    int w = settings.width(), h = settings.height(), fh = settings.fontHeight();
    List<byte[]> commands = new ArrayList<>();
    if (settings.ipixel() && h != 16) throw new IllegalArgumentException("iPixel height must be 16");
    if (!settings.ipixel()) commands.add(new byte[] {0x30, 1, (byte) 0x90});
    if (!settings.ipixel()) commands.add(LoyProtocol.clear(w, h));
    if (style == null || style.text.isEmpty() || (!settings.ipixel() && style.effect == 1 && tick % 2 == 1)) {
      if (settings.ipixel()) commands.add(IPixelProtocol.text(new byte[((w+7)/8)*h],w,h,0,0));
      return commands;
    }
    if (style.effect >= 11 && style.effect < 11+EyeAnimations.NAMES.length) {
      if(nativeEyes){commands.add(IPixelProtocol.gif(EyeAnimations.gif(settings.context,style.effect-11,style.color)));return commands;}
      Bitmap eye=EyeAnimations.raster(settings.context,style.effect-11,style.color,w,h,tick*200);
      if(eye==null)throw new IllegalArgumentException("eyes asset unavailable");
      byte[][] layers=new byte[4][((w+7)/8)*h];
      boolean fixed=style.effect>=17;
      int[] palette=fixed?new int[]{0xffff2236,0xff680719,0xff944dd9,0xffc68cfa}:null;
      int peak=Math.max(Color.red(style.color),Math.max(Color.green(style.color),Color.blue(style.color)));
      for(int y=0;y<h;y++)for(int x=0;x<w;x++){
        int c=eye.getPixel(x,y), red=Color.red(c),green=Color.green(c),blue=Color.blue(c);
        int value=Math.max(red,Math.max(green,blue));if(value<(fixed?85:10))continue;
        boolean white=red>Color.red(style.color)+12 || green>Color.green(style.color)+12 || blue>Color.blue(style.color)+12;
        int layer=white?3:value<peak/3?0:value<peak*2/3?1:2;
        if(fixed){
          int best=Integer.MAX_VALUE;
          for(int j=0;j<palette.length;j++){int dr=red-Color.red(palette[j]),dg=green-Color.green(palette[j]),db=blue-Color.blue(palette[j]);int distance=dr*dr+dg*dg+db*db;if(distance<best){best=distance;layer=j;}}
        }
        layers[layer][y*((w+7)/8)+x/8]|=(byte)(128>>(x%8));
      }
      eye.recycle();
      if(settings.ipixel()){
        // Small-MTU/compatibility mode remains one colored bitmap, avoiding a long GIF transfer.
        byte[] merged=new byte[layers[0].length];for(byte[] layer:layers)for(int i=0;i<merged.length;i++)merged[i]|=layer[i];
        commands.add(IPixelProtocol.text(merged,w,h,fixed?0xff2236:style.color,0));
      }else for(int level=0;level<4;level++){
        int color=fixed?palette[level]:level==3?Color.WHITE:Color.rgb(Color.red(style.color)*(level+1)/3,Color.green(style.color)*(level+1)/3,Color.blue(style.color)*(level+1)/3);
        commands.addAll(LoyProtocol.pixels(layers[level],w,h,color));
      }
      return commands;
    }
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
    if (bounds.height() == 0) {
      if (settings.ipixel()) commands.add(IPixelProtocol.text(new byte[((w+7)/8)*h],w,h,0,0));
      return commands;
    }
    float scale = (float) fh / bounds.height();
    float sx = scale * settings.fontWidth() / 100f;
    float advance = p.measureText(style.text);
    float natural = Math.max(advance, bounds.right) - Math.min(0, bounds.left);
    boolean scrolling = style.effect == 2 || style.effect == 3;
    int textWidth = style.effect >= 6 ? w * 68 / 96 : w;
    if (!scrolling && natural * sx > textWidth) sx = textWidth / natural;
    int tw = Math.max(1, (int) Math.ceil(natural * sx));
    boolean nativeScroll = settings.ipixel() && scrolling;
    if (nativeScroll) w = Math.min(2040, ((tw+7)/8)*8);
    Bitmap bitmap = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
    Canvas c = new Canvas(bitmap);
    c.drawColor(Color.BLACK);
    float y = (h - fh) / 2f;
    if (scrolling && !nativeScroll) {
      int span = tw + w;
      int progress = (int) ((tick * 2) % span);
      float x = style.effect == 2 ? w - progress : progress - tw;
      c.save();
      c.translate(x, y);
      c.scale(sx, scale);
      c.drawText(style.text, -Math.min(0, bounds.left), -bounds.top, p);
      c.restore();
    } else {
      c.save();
      c.translate(nativeScroll ? 0 : (w - tw) / 2f, y);
      c.scale(sx, scale);
      c.drawText(style.text, -Math.min(0, bounds.left), -bounds.top, p);
    }
    if (!scrolling || nativeScroll) c.restore();
    if (style.effect >= 6) pattern(c, p, style.effect, tick, w, h);
    byte[] bits = new byte[((w + 7) / 8) * h];
    for (int yy = 0; yy < h; yy++)
      for (int x = 0; x < w; x++)
        if (Color.red(bitmap.getPixel(x, yy)) > 60)
          bits[yy * ((w + 7) / 8) + x / 8] |= (byte) (128 >> (x % 8));
    bitmap.recycle();
    int color = style.color;
    if (!settings.ipixel() && style.effect == 4) {
      double[] levels = {.25, .4, .6, .8, 1, .8, .6, .4};
      double n = levels[(int) (tick % 8)];
      color =
          Color.rgb(
              (int) (Color.red(color) * n),
              (int) (Color.green(color) * n),
              (int) (Color.blue(color) * n));
    }
    if (!settings.ipixel() && style.effect == 5) color = Color.HSVToColor(new float[] {(tick % 12) * 30, 1, 1});
    if (settings.ipixel()) commands.add(IPixelProtocol.text(bits,w,h,color,style.effect));
    else commands.addAll(LoyProtocol.pixels(bits, w, h, color));
    return commands;
  }
}
