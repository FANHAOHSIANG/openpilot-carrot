package tw.carrot.led;

import android.app.*;
import android.content.*;
import android.content.pm.ServiceInfo;
import android.net.*;
import android.os.*;
import java.io.*;
import java.net.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

public final class LedService extends Service {
  public static final String START = "START",
      STOP = "STOP",
      CLEAR = "CLEAR",
      AUTO = "AUTO",
      CUSTOM = "CUSTOM",
      PREVIEW = "PREVIEW",
      SCAN = "SCAN",
      CONNECT = "CONNECT",
      POWER = "POWER",
      RELOAD = "RELOAD",
      TEST = "TEST", EYES = "EYES";
  public static volatile String status = "服務未啟動", details = "", screen = "屏幕尚未連線", display = "清屏";
  public static volatile boolean running = false, connected = false, automatic = false, powerOn = false;
  public static volatile Map<String, String> discovered = Collections.emptyMap();
  HandlerThread thread;
  Handler h;
  ExecutorService network;
  Settings settings;
  BleLink ble;
  PowerManager.WakeLock wake;
  volatile boolean stopping = false;
  boolean polling = false;
  long lastSample = -1, startTime, lastNotification = 0, lastRender = 0, lastPoll = -200;
  int generation = 0, slot = -1;
  String previewKey = "";
  long previewUntil = 0;
  public static volatile String previewStatus = "";
  String host = "", token = "", label = "", lastKey = "";
  final VehicleRules rules = new VehicleRules();
  final StartupPlayback startup = new StartupPlayback();

  public void onCreate() {
    super.onCreate();
    settings = new Settings(this);
    thread = new HandlerThread("CarrotLED");
    thread.start();
    h = new Handler(thread.getLooper());
    network = Executors.newSingleThreadExecutor();
    ble = new BleLink(this, h, settings);
    ble.onReady =
        () -> {
          lastKey = "";
          automatic = true; powerOn = true;
          ble.controls(Collections.singletonList(settings.ipixel() ? IPixelProtocol.power(true) : new byte[] {4, 2, 0, 1}));
          if(StartupArtwork.supported(settings.width(),settings.height())) startup.begin(SystemClock.elapsedRealtime());
        };
    getSystemService(NotificationManager.class)
        .createNotificationChannel(
            new NotificationChannel("drive", "行車 LED 連動", NotificationManager.IMPORTANCE_LOW));
  }

  public int onStartCommand(Intent intent, int flags, int startId) {
    String action = intent == null ? STOP : intent.getAction();
    if (START.equals(action)) {
      try {
        Notification n = notification("正在啟動連動");
        if (Build.VERSION.SDK_INT >= 29)
          startForeground(7, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE);
        else startForeground(7, n);
      } catch (Exception e) {
        status = "無法啟動背景服務，請檢查附近裝置權限";
        stopSelf();
        return START_NOT_STICKY;
      }
      h.post(
          () -> {
            if (stopping) return;
            reload();
            if (running) return;
            running = true;
            automatic = true;
            slot = -1;
            startTime = SystemClock.elapsedRealtime();
            wake =
                ((PowerManager) getSystemService(POWER_SERVICE))
                    .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "CarrotLED:driving");
            wake.acquire(8 * 60 * 60 * 1000L);
            ble.start();
            h.post(tick);
          });
    } else h.post(() -> command(action, intent));
    return START_NOT_STICKY;
  }

  private void reload() {
    generation++;
    lastSample = -1;
    rules.reset();
    host = settings.host();
    try {
      token = settings.token();
    } catch (Exception e) {
      token = "";
      status = "金鑰讀取失敗，請重新儲存";
    }
    lastKey = "";
  }

  private void command(String a, Intent i) {
    if (stopping) return;
    // Explicit content, clear, settings, scan and stop always supersede the opener.
    if (!POWER.equals(a)) startup.cancel();
    if (STOP.equals(a)) {
      shutdown();
      return;
    }
    if (!running) return;
    if (CLEAR.equals(a)) {
      previewKey = "";
      previewStatus = "";
      automatic = false;
      slot = -1;
      label = "";
      lastKey = "";
      render(true);
    }
    if ((AUTO.equals(a) && i.getBooleanExtra("enabled",true)) || PREVIEW.equals(a) || CUSTOM.equals(a) || EYES.equals(a) || TEST.equals(a)) {
      if (ble.ready && !powerOn) {
        powerOn=true;
        ble.controls(Collections.singletonList(settings.ipixel()?IPixelProtocol.power(true):new byte[]{4,2,0,1}));
      }
    }
    if (EYES.equals(a)) {
      previewKey="";previewStatus="";slot=5;lastKey="";render(true);
    }
    if (AUTO.equals(a)) {
      previewKey = "";
      previewStatus = "";
      automatic = i.getBooleanExtra("enabled", true);
      lastKey = "";
      render(true);
    }
    if (PREVIEW.equals(a)) {
      String key = i.getStringExtra("event");
      if (Arrays.asList(Settings.EVENTS).contains(key) && ble.ready) {
        previewKey = key;
        previewUntil = SystemClock.elapsedRealtime() + 5000;
        previewStatus = "手動預覽：" + Settings.title(key) + "（5 秒，暫停自動顯示）";
        lastKey = "";
        render(true);
      }
    }
    if (CUSTOM.equals(a)) {
      previewKey = "";
      previewStatus = "";
      slot = i.getIntExtra("slot", -1);
      lastKey = "";
    }
    if (SCAN.equals(a)) {
      ble.close();
      ble.closed = false;
      ble.scan();
    }
    if (CONNECT.equals(a)) {
      String addr = i.getStringExtra("address");
      if (addr != null) ble.connect(addr);
    }
    if (RELOAD.equals(a)) reload();
    if (POWER.equals(a)) {
      previewKey = "";
      previewStatus = "";
      boolean on = i.getBooleanExtra("on", true);
      boolean wasOn = powerOn;
      if(!on) startup.cancel();
      if (!on) {
        automatic = false;
        slot = -1;
      }
      lastKey = "";
      powerOn = on && ble.ready;
      ble.controls(
          settings.ipixel() ? Collections.singletonList(IPixelProtocol.power(on)) : Arrays.asList(new byte[] {0x30, 1, 0x65}, new byte[] {4, 2, 0, (byte) (on ? 1 : 0)}));
      display = on ? "已送開屏" : "已送關屏";
      if(on && !wasOn && ble.ready && StartupArtwork.supported(settings.width(),settings.height()))
        startup.begin(SystemClock.elapsedRealtime());
    }
    if (TEST.equals(a)) {
      previewKey = "";
      previewStatus = "";
      automatic = false;
      slot = -1;
      int w = settings.width(), height = settings.height();
      byte[] bits = new byte[((w + 7) / 8) * height];
      Arrays.fill(bits, (byte) 255);
      List<byte[]> c = new ArrayList<>();
      if (settings.ipixel()) c.add(IPixelProtocol.text(bits,w,height,0xffffff,0));
      else { c.add(new byte[] {0x30,1,(byte)0x90}); c.addAll(LoyProtocol.pixels(bits,w,height,0xffffff)); }
      ble.offer(c);
      lastKey = "test";
      display = "全亮測試，按清屏結束";
    }
  }

  final Runnable tick =
      new Runnable() {
        public void run() {
          if (stopping || !running) return;
          long now = SystemClock.elapsedRealtime();
          if (now - startTime >= 8 * 60 * 60 * 1000L) {
            status = "行車連動已滿 8 小時，請重新開始";
            shutdown();
            return;
          }
          if (lastSample >= 0 && now - lastSample >= 900) {
            lastSample = -1;
            label = "";
            rules.reset();
            status = "C4 資料過期，嘗試清屏";
            lastKey = "";
          }
          if (!polling && now - lastPoll >= 200) { lastPoll = now; poll(); }
          if (now - lastRender >= 50) {
            lastRender = now;
            if (!previewKey.isEmpty() && now >= previewUntil) {
              previewKey = "";
              previewStatus = "";
              lastKey = "";
              render(true);
            }
            if (startup.active || automatic || slot >= 0 || !previewKey.isEmpty()) render(false);
          }
          screen = ble.status;
          connected = ble.ready;
          if (!connected) { powerOn = false; startup.cancel(); }
          discovered = Collections.unmodifiableMap(new LinkedHashMap<>(ble.devices));
          if (now - lastNotification >= 2000) {
            lastNotification = now;
            getSystemService(NotificationManager.class)
                .notify(7, notification(status + " · " + (ble.ready ? "藍牙已連線" : "屏幕未連線")));
          }
          h.postDelayed(this, 50);
        }
      };

  private void poll() {
    if (!Settings.privateIP(host) || !token.matches("[A-Za-z0-9]{20,128}")) {
      status = "請儲存 C4 區網 IP 與金鑰";
      return;
    }
    polling = true;
    int id = generation;
    String address = host, bearer = token;
    long requested = SystemClock.elapsedRealtime();
    network.execute(
        () -> {
          JSONObject data = null;
          String error = "C4 資料中斷，重試中";
          HttpURLConnection c = null;
          try {
            URL url = new URL("http://" + address + ":18765/carstate");
            ConnectivityManager cm = getSystemService(ConnectivityManager.class);
            Network wifi = null;
            for (Network n : cm.getAllNetworks()) {
              NetworkCapabilities caps = cm.getNetworkCapabilities(n);
              if (caps != null && caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) {
                wifi = n;
                break;
              }
            }
            c =
                (HttpURLConnection)
                    (wifi == null ? url.openConnection() : wifi.openConnection(url));
            c.setConnectTimeout(600);
            c.setReadTimeout(600);
            c.setInstanceFollowRedirects(false);
            c.setUseCaches(false);
            c.setRequestProperty("Authorization", "Bearer " + bearer);
            int code = c.getResponseCode();
            if (code == 401) {
              error = "C4 金鑰錯誤，請重新輸入";
            } else if (code == 200) {
              ByteArrayOutputStream b = new ByteArrayOutputStream();
              try (InputStream in = c.getInputStream()) {
                byte[] block = new byte[1024];
                int n;
                while ((n = in.read(block)) != -1) {
                  if (b.size() + n > 8192) throw new IOException("response too large");
                  b.write(block, 0, n);
                }
              }
              data = new JSONObject(b.toString("UTF-8"));
            }
          } catch (Exception ignored) {
          } finally {
            if (c != null) c.disconnect();
          }
          final JSONObject result = data;
          final String message = error;
          h.post(
              () -> {
                polling = false;
                if (stopping || id != generation) return;
                long now = SystemClock.elapsedRealtime();
                try {
                  if (result == null || !result.getBoolean("valid") || now - requested >= 900)
                    throw new JSONException("invalid");
                  double speed = result.getDouble("speed"), accel = result.getDouble("accel");
                  if (!Double.isFinite(speed) || !Double.isFinite(accel))
                    throw new JSONException("nonfinite");
                  boolean brake = result.getBoolean("brake"),
                      left = result.getBoolean("left"),
                      right = result.getBoolean("right");
                  String gear = result.getString("gear").toLowerCase(Locale.ROOT);
                  lastSample = now;
                  label = rules.choose(speed, accel, brake, left, right, gear, now);
                  if(automatic && rules.emergencyActive){previewKey="";previewStatus="";}
                  status = "已收到 C4 車況";
                  details =
                      String.format(
                          Locale.TAIWAN,
                          "%.1f km/h  %.2f m/s²  %s\n煞車 %s｜左燈 %s｜右燈 %s",
                          speed * 3.6,
                          accel,
                          gear,
                          brake,
                          left,
                          right);
                } catch (Exception e) {
                  lastSample = -1;
                  rules.reset();
                  label = "";
                  status = message;
                  details = "等待有效車況";
                  if (automatic) render(true);
                }
              });
        });
  }

  private void render(boolean force) {
    if (!ble.ready || (!powerOn && !force)) return;
    boolean fresh = lastSample >= 0 && SystemClock.elapsedRealtime() - lastSample < 900;
    if (startup.active) {
      int frame = startup.step(SystemClock.elapsedRealtime(), ble.ready, powerOn,
          automatic && fresh && !label.isEmpty(), ble.idle(),
          settings.ipixel() && settings.width()==64 && settings.p.getBoolean("eyes.native",true) && ble.nativeEyesReady(), settings.ipixel()?200:50);
      if (frame >= 0 || frame == StartupPlayback.NATIVE) {
        try { ble.offer(StartupArtwork.commands(settings,frame)); display="胡蘿蔔車開走 · 開屏動畫"; }
        catch (IllegalArgumentException e) { startup.cancel(); screen="開屏動畫略過："+e.getMessage(); }
      }
      if (startup.active) return;
      lastKey=""; // Resume the current vehicle/custom state, never an old snapshot.
    }
    String key =
        DisplaySelection.choose(
            automatic, fresh, label, slot, previewKey, previewUntil, SystemClock.elapsedRealtime());
    Settings.Style style = key.isEmpty() ? null : settings.style(key);
    boolean nativeEyes=key.equals("eyes") && settings.ipixel() && settings.width()==64 && settings.height()==16 && settings.p.getBoolean("eyes.native",true) && ble.nativeEyesReady();
    // Never queue old animation bitmaps behind a busy link. Sample the current
    // animation time only once the previous frame and any vehicle alert are done.
    if (key.equals("eyes") && !nativeEyes && !ble.idle()) return;
    long phase = SystemClock.elapsedRealtime() / (key.equals("eyes")?(settings.ipixel()?200:50):333);
    String signature =
        key
            + (style == null
                ? ""
                : style.text
                    + style.color
                    + style.font
                    + style.bold
                    + style.effect
                    + (nativeEyes || style.effect == 0 || (settings.ipixel() && style.effect <= 5) ? 0 : phase));
    if (!force && signature.equals(lastKey)) return;
    lastKey = signature;
    display = style == null ? "清屏" : key.equals("eyes") ? EyeAnimations.NAMES[EyeAnimations.index(style.effect-11)] : style.text;
    try { ble.offer(LedRenderer.render(settings, style, phase,nativeEyes)); }
    catch (IllegalArgumentException e) { screen = "顯示失敗："+e.getMessage(); lastKey=""; }
  }

  private Notification notification(String text) {
    PendingIntent open =
        PendingIntent.getActivity(
            this,
            0,
            new Intent(this, MainActivity.class),
            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    PendingIntent clear =
        PendingIntent.getService(
            this,
            1,
            new Intent(this, LedService.class).setAction(CLEAR),
            PendingIntent.FLAG_IMMUTABLE);
    PendingIntent stop =
        PendingIntent.getService(
            this,
            2,
            new Intent(this, LedService.class).setAction(STOP),
            PendingIntent.FLAG_IMMUTABLE);
    return new Notification.Builder(this, "drive")
        .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth)
        .setContentTitle("Carrot LED 行車連動")
        .setContentText(text)
        .setContentIntent(open)
        .setOngoing(true)
        .setOnlyAlertOnce(true)
        .addAction(new Notification.Action.Builder(null, "清屏", clear).build())
        .addAction(new Notification.Action.Builder(null, "停止", stop).build())
        .build();
  }

  private void shutdown() {
    if (stopping) return;
    stopping = true;
    previewKey = "";
    previewStatus = "";
    generation++;
    automatic = false;
    slot = -1;
    h.removeCallbacks(tick);
    ble.offer(LedRenderer.render(settings, null, 0,false));
    long until = SystemClock.elapsedRealtime() + 1800;
    Runnable finish =
        new Runnable() {
          public void run() {
            if (ble.ready && !ble.idle() && SystemClock.elapsedRealtime() < until) {
              h.postDelayed(this, 50);
              return;
            }
            ble.close();
            stopForeground(STOP_FOREGROUND_REMOVE);
            stopSelf();
          }
        };
    h.postDelayed(finish, 50);
  }

  public void onDestroy() {
    stopping = true;
    running = false;
    connected = false;
    powerOn = false;
    automatic = false;
    screen = "服務已停止，請確認屏幕已清除";
    if (wake != null && wake.isHeld()) wake.release();
    network.shutdownNow();
    h.post(
        () -> {
          ble.close();
          thread.quitSafely();
        });
    super.onDestroy();
  }

  public IBinder onBind(Intent intent) {
    return null;
  }
}
