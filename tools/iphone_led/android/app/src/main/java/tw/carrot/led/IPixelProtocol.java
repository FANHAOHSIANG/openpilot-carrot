package tw.carrot.led;

import java.io.ByteArrayOutputStream;
import java.util.zip.CRC32;

/** iPixel FA02 text upload, transient slot 0; never erases device ROM. */
public final class IPixelProtocol {
  public static byte[] power(boolean on) { return new byte[] {5, 0, 7, 1, (byte)(on ? 1 : 0)}; }
  public static boolean ack(byte[] b) {
    return b != null && b.length == 5 && b[0] == 5 && b[1] == 0
        && (b[4] == 0 || b[4] == 1 || b[4] == 3);
  }
  public static int animation(int effect) {
    return effect == 1 ? 5 : effect == 2 ? 1 : effect == 3 ? 2 : effect == 4 ? 6 : 0;
  }
  private static void le(ByteArrayOutputStream b, long n, int count) {
    for (int i=0;i<count;i++) b.write((int)(n >> (8*i)) & 255);
  }
  /** Single-window GIF, matching pypixelcolor send_image._build_send_plan; transient slot 0. */
  public static byte[] gif(byte[] data) {
    if(data==null || data.length<61 || data.length>8192 || data[0]!='G' || data[1]!='I' || data[2]!='F'
        || data[6]!=64 || data[7]!=0 || data[8]!=16 || data[9]!=0 || data[data.length-1]!=0x3b)
      throw new IllegalArgumentException("native eyes require a bounded 64x16 GIF");
    CRC32 crc=new CRC32();crc.update(data);ByteArrayOutputStream frame=new ByteArrayOutputStream();
    le(frame,data.length+15,2);frame.write(3);frame.write(0);frame.write(0);
    le(frame,data.length,4);le(frame,crc.getValue(),4);frame.write(2);frame.write(0);
    frame.write(data,0,data.length);return frame.toByteArray();
  }
  public static byte[] text(byte[] bitmap, int width, int height, int color, int effect) {
    if (height != 16 || width < 1 || width > 2040 || bitmap.length != ((width+7)/8)*16)
      throw new IllegalArgumentException("iPixel requires 16 rows and at most 255 eight-pixel blocks");
    int cols=(width+7)/8;
    ByteArrayOutputStream data=new ByteArrayOutputStream();
    data.write(cols);
    byte[] rgb={(byte)(color>>16),(byte)(color>>8),(byte)color};
    byte[] props={0,1,1,(byte)animation(effect),80,(byte)(effect==5?1:0),rgb[0],rgb[1],rgb[2],1,0,0,0};
    data.write(props,0,props.length);
    for (int i=0;i<cols;i++) {
      int x=effect==3?cols-1-i:i;
      data.write(0); data.write(rgb,0,3);
      for (int y=0;y<16;y++) data.write(Integer.reverse(bitmap[y*cols+x]&255)>>>24);
    }
    byte[] payload=data.toByteArray(); CRC32 crc=new CRC32();crc.update(payload);
    ByteArrayOutputStream frame=new ByteArrayOutputStream();
    le(frame,payload.length+15,2); frame.write(0);frame.write(1);frame.write(0);
    le(frame,payload.length,4);le(frame,crc.getValue(),4);frame.write(0);frame.write(0);
    frame.write(payload,0,payload.length);return frame.toByteArray();
  }
}
