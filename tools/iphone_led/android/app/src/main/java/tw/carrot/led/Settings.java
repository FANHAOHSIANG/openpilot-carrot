package tw.carrot.led;

import android.content.*;
import android.graphics.Color;
import android.security.keystore.*;
import android.util.Base64;
import java.security.KeyStore;
import javax.crypto.*;
import javax.crypto.spec.GCMParameterSpec;

final class Settings {
  static final String[] EVENTS = {"倒車", "左轉彎", "右轉彎", "減速中", "暫停一下謝謝", "謝謝", "前方塞車"};
  static final String[] TITLES = {"R檔", "左方向燈", "右方向燈", "煞車", "雙黃燈", "感謝燈", "急煞雙黃燈"};

  static String title(String key) {
    for (int i = 0; i < EVENTS.length; i++) if (EVENTS[i].equals(key)) return TITLES[i];
    return key;
  }

  static final String[] EFFECTS = {
    "靜態", "閃爍", "向左跑馬燈", "向右跑馬燈", "呼吸", "自動換色", "向左動態箭頭", "向右動態箭頭", "波浪圖案", "愛心圖案", "警示圖案"
  };
  static final String[] FONTS = {"系統黑體", "襯線體", "等寬體", "圓潤黑體", "匯入字型"};
  final SharedPreferences p;
  final java.io.File fontFile;

  Settings(Context c) {
    fontFile = new java.io.File(c.getFilesDir(), "user-font");
    p = c.getSharedPreferences("settings", Context.MODE_PRIVATE);
  }

  String host() {
    return p.getString("host", "");
  }

  int width() {
    return p.getInt("width", 96);
  }

  int height() {
    return p.getInt("height", 16);
  }

  int fontHeight() {
    return Math.min(height(), p.getInt("fontHeight", 16));
  }

  int fontWidth() {
    return p.getInt("fontWidth", 100);
  }

  static class Style {
    String text;
    int color, effect, font;
    boolean bold;

    Style(String t, int c, int e, int f, boolean b) {
      text = t;
      color = c;
      effect = e;
      font = f;
      bold = b;
    }
  }

  Style style(String key) {
    return new Style(
        p.getString(key + ".text", key.startsWith("slot") ? "" : key.equals("倒車") ? "倒車，請注意" : key),
        p.getInt(
            key + ".color", key.equals("減速中") ? Color.rgb(255, 48, 32) : Color.rgb(255, 180, 0)),
        p.getInt(key + ".effect", 0),
        p.getInt(key + ".font", 0),
        p.getBoolean(key + ".bold", false));
  }

  void save(String key, Style s) {
    p.edit()
        .putString(key + ".text", s.text)
        .putInt(key + ".color", s.color)
        .putInt(key + ".effect", s.effect)
        .putInt(key + ".font", s.font)
        .putBoolean(key + ".bold", s.bold)
        .apply();
  }

  private SecretKey secret() throws Exception {
    KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
    ks.load(null);
    String alias = "carrot-led-bridge";
    if (!ks.containsAlias(alias)) {
      KeyGenerator g = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
      g.init(
          new KeyGenParameterSpec.Builder(
                  alias, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
              .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
              .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
              .build());
      g.generateKey();
    }
    return (SecretKey) ks.getKey(alias, null);
  }

  void saveToken(String token) throws Exception {
    Cipher c = Cipher.getInstance("AES/GCM/NoPadding");
    c.init(Cipher.ENCRYPT_MODE, secret());
    p.edit()
        .putString(
            "token", Base64.encodeToString(c.doFinal(token.getBytes("UTF-8")), Base64.NO_WRAP))
        .putString("iv", Base64.encodeToString(c.getIV(), Base64.NO_WRAP))
        .commit();
  }

  String token() throws Exception {
    if (!p.contains("token")) return "";
    Cipher c = Cipher.getInstance("AES/GCM/NoPadding");
    c.init(
        Cipher.DECRYPT_MODE,
        secret(),
        new GCMParameterSpec(128, Base64.decode(p.getString("iv", ""), Base64.NO_WRAP)));
    return new String(c.doFinal(Base64.decode(p.getString("token", ""), Base64.NO_WRAP)), "UTF-8");
  }

  static boolean privateIP(String s) {
    String[] a = s.split("\\.", -1);
    if (a.length != 4) return false;
    int[] v = new int[4];
    try {
      for (int i = 0; i < 4; i++) {
        if (!a[i].matches("[0-9]{1,3}")) return false;
        v[i] = Integer.parseInt(a[i]);
        if (v[i] > 255) return false;
      }
    } catch (Exception e) {
      return false;
    }
    return v[0] == 10 || (v[0] == 172 && v[1] >= 16 && v[1] <= 31) || (v[0] == 192 && v[1] == 168);
  }
}
