package tw.carrot.led;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.*;
import android.os.*;
import android.text.InputType;
import android.view.*;
import android.view.inputmethod.InputMethodManager;
import android.widget.*;
import java.io.*;
import java.util.*;

public final class MainActivity extends Activity {
  Settings settings;
  LinearLayout body;
  TextView state;
  Switch autoSwitch;
  boolean syncingAuto;
  final Map<String, TextView> quickLabels = new HashMap<>();
  EditText host, token;
  Handler ui = new Handler();
  int selectedPage = 0;
  final ArrayList<ScrollView> pages = new ArrayList<>();
  final ArrayList<Button> tabs = new ArrayList<>();

  int dp(float value) {
    return Math.round(value * getResources().getDisplayMetrics().density);
  }

  LinearLayout panel() {
    LinearLayout box = new LinearLayout(this);
    box.setOrientation(LinearLayout.VERTICAL);
    box.setPadding(dp(12), dp(8), dp(12), dp(8));
    return box;
  }

  void hideKeyboard() {
    View focus = getCurrentFocus();
    if (focus != null) {
      ((InputMethodManager) getSystemService(INPUT_METHOD_SERVICE))
          .hideSoftInputFromWindow(focus.getWindowToken(), 0);
      focus.clearFocus();
    }
  }

  void selectPage(int index) {
    hideKeyboard();
    selectedPage = index;
    for (int i = 0; i < pages.size(); i++) {
      pages.get(i).setVisibility(i == index ? View.VISIBLE : View.GONE);
      tabs.get(i).setTextColor(i == index ? Color.WHITE : Color.rgb(52, 62, 57));
      tabs.get(i)
          .setBackgroundTintList(
              android.content.res.ColorStateList.valueOf(
                  i == index ? Color.rgb(171, 65, 20) : Color.rgb(238, 230, 220)));
    }
  }

  void addPage(LinearLayout content, LinearLayout navigation, String title, Runnable populate) {
    int index = pages.size();
    Button tab = new Button(this);
    tab.setText(title);
    tab.setTextSize(16);
    tab.setMinHeight(dp(52));
    tab.setOnClickListener(v -> selectPage(index));
    navigation.addView(tab, new LinearLayout.LayoutParams(dp(100), dp(56)));
    tabs.add(tab);
    ScrollView scroll = new ScrollView(this);
    scroll.setFillViewport(true);
    body = panel();
    scroll.addView(body);
    populate.run();
    pages.add(scroll);
    content.addView(scroll, new LinearLayout.LayoutParams(-1, -1));
  }

  void startSession() {
    if (!saveConnection()) {
      selectPage(1);
      return;
    }
    if (!permissions()) {
      requestPermissions(required(), 42);
      return;
    }
    begin();
  }

  protected void onSaveInstanceState(Bundle out) {
    out.putInt("page", selectedPage);
    out.putString("hostDraft", host.getText().toString());
    super.onSaveInstanceState(out);
  }

  void text(String s, int size) {
    TextView v = new TextView(this);
    v.setText(s);
    v.setTextSize(size);
    v.setPadding(0, dp(12), 0, dp(6));
    body.addView(v);
  }

  Button button(String s, Runnable action) {
    Button b = new Button(this);
    b.setText(s);
    b.setAllCaps(false);
    b.setTextSize(18);
    b.setMinHeight(dp(56));
    b.setOnClickListener(v -> action.run());
    body.addView(b);
    return b;
  }

  EditText field(LinearLayout box, String hint, String value, int type) {
    EditText e = new EditText(this);
    e.setHint(hint);
    e.setText(value);
    e.setInputType(type);
    e.setSingleLine(true);
    e.setMinHeight(dp(56));
    e.setTextSize(18);
    e.setImeOptions(android.view.inputmethod.EditorInfo.IME_ACTION_DONE);
    e.setOnEditorActionListener(
        (view, action, event) -> {
          if (action == android.view.inputmethod.EditorInfo.IME_ACTION_DONE) {
            hideKeyboard();
            return true;
          }
          return false;
        });
    box.addView(e, new LinearLayout.LayoutParams(-1, -2));
    return e;
  }

  public void onCreate(Bundle b) {
    super.onCreate(b);
    settings = new Settings(this);
    boolean wide =
        getResources().getConfiguration().screenWidthDp >= 700
            && getResources().getConfiguration().screenWidthDp
                > getResources().getConfiguration().screenHeightDp;
    LinearLayout root = new LinearLayout(this);
    root.setOrientation(wide ? LinearLayout.HORIZONTAL : LinearLayout.VERTICAL);
    root.setBackgroundColor(Color.rgb(255, 247, 240));
    setContentView(root);
    root.setOnApplyWindowInsetsListener(
        (v, insets) -> {
          if (Build.VERSION.SDK_INT >= 30) {
            android.graphics.Insets bars =
                insets.getInsets(
                    WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
            android.graphics.Insets ime = insets.getInsets(WindowInsets.Type.ime());
            v.setPadding(bars.left, bars.top, bars.right, Math.max(bars.bottom, ime.bottom));
          } else
            v.setPadding(
                insets.getSystemWindowInsetLeft(),
                insets.getSystemWindowInsetTop(),
                insets.getSystemWindowInsetRight(),
                insets.getSystemWindowInsetBottom());
          return insets;
        });
    root.requestApplyInsets();
    LinearLayout dashboard = panel();
    root.addView(
        dashboard,
        wide
            ? new LinearLayout.LayoutParams(0, -1, .36f)
            : new LinearLayout.LayoutParams(-1, dp(220)));
    ScrollView controls = new ScrollView(this);
    dashboard.addView(controls, new LinearLayout.LayoutParams(-1, 0, 1));
    body = panel();
    controls.addView(body);
    text("Carrot LED", 26);
    text(wide ? "車機橫向介面 · 0.1.2" : "自適應介面 · 0.1.2", 14);
    state = new TextView(this);
    state.setTextSize(16);
    state.setPadding(dp(8), dp(8), dp(8), dp(8));
    state.setBackgroundColor(Color.WHITE);
    body.addView(state);
    button("開始背景連動", () -> startSession());
    button("停止背景連動", () -> send(LedService.STOP));
    autoSwitch = new Switch(this);
    autoSwitch.setText("自動車況");
    autoSwitch.setTextSize(20);
    autoSwitch.setMinHeight(dp(56));
    autoSwitch.setOnCheckedChangeListener(
        (v, checked) -> {
          if (!syncingAuto)
            send(
                new Intent(this, LedService.class)
                    .setAction(LedService.AUTO)
                    .putExtra("enabled", checked));
        });
    body.addView(autoSwitch);
    LinearLayout old = body;
    body = dashboard;
    Button clear = button("清屏 · 暫停所有顯示", () -> send(LedService.CLEAR));
    clear.setTextColor(Color.WHITE);
    clear.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Color.rgb(171, 65, 20)));
    body = old;

    LinearLayout editor = panel();
    root.addView(
        editor,
        wide
            ? new LinearLayout.LayoutParams(0, -1, .64f)
            : new LinearLayout.LayoutParams(-1, 0, 1));
    HorizontalScrollView tabScroll = new HorizontalScrollView(this);
    tabScroll.setHorizontalScrollBarEnabled(false);
    LinearLayout navigation = new LinearLayout(this);
    navigation.setOrientation(LinearLayout.HORIZONTAL);
    tabScroll.addView(navigation);
    editor.addView(tabScroll, new LinearLayout.LayoutParams(-1, dp(60)));
    LinearLayout content = new LinearLayout(this);
    content.setOrientation(LinearLayout.VERTICAL);
    editor.addView(content, new LinearLayout.LayoutParams(-1, 0, 1));
    addPage(
        content,
        navigation,
        "快捷",
        () -> {
          text("車況快捷預覽", 22);
          text("預覽 5 秒後恢復原模式。請停車操作；目前送出內容並非屏幕回讀。", 16);
          for (String event : Settings.EVENTS)
            quickRow(
                event,
                Settings.title(event),
                () ->
                    send(
                        new Intent(this, LedService.class)
                            .setAction(LedService.PREVIEW)
                            .putExtra("event", event)));
          text("五組自訂文字", 22);
          for (int i = 0; i < 5; i++) {
            final int n = i;
            quickRow(
                "slot" + n,
                "自訂 " + (n + 1),
                () ->
                    send(
                        new Intent(this, LedService.class)
                            .setAction(LedService.CUSTOM)
                            .putExtra("slot", n)));
          }
        });
    addPage(
        content,
        navigation,
        "連線",
        () -> {
          text("C4 連線設定", 22);
          host =
              field(
                  body,
                  "C4 區網 IP，例如 192.168.1.138",
                  b == null ? settings.host() : b.getString("hostDraft", settings.host()),
                  InputType.TYPE_CLASS_PHONE);
          token =
              field(
                  body,
                  "橋接金鑰（已儲存可留空）",
                  "",
                  InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
          token.setSaveEnabled(false);
          button("儲存連線設定", () -> saveConnection());
          button("收起鍵盤", () -> hideKeyboard());
          text("C4 與車機接入同一區網，沿用原橋接金鑰。按「開始背景連動」後再連接屏幕。", 16);
          text("系統檢查", 20);
          android.bluetooth.BluetoothManager bm =
              getSystemService(android.bluetooth.BluetoothManager.class);
          boolean ble = getPackageManager().hasSystemFeature(PackageManager.FEATURE_BLUETOOTH_LE);
          text(
              "Android "
                  + Build.VERSION.RELEASE
                  + " · API "
                  + Build.VERSION.SDK_INT
                  + "\n視窗 "
                  + getResources().getConfiguration().screenWidthDp
                  + " × "
                  + getResources().getConfiguration().screenHeightDp
                  + " dp"
                  + "\n系統宣告 BLE："
                  + (ble ? "支援" : "未宣告")
                  + "\n藍牙介面："
                  + (bm != null && bm.getAdapter() != null ? "存在，仍需實際連線確認" : "不可用"),
              16);
        });
    addPage(
        content,
        navigation,
        "屏幕",
        () -> {
          text("屏幕控制", 22);
          button(
              "掃描屏幕",
              () -> {
                if (!LedService.running) {
                  toast("請先開始背景連動");
                  return;
                }
                send(LedService.SCAN);
                toast("掃描約 12 秒，再按選擇屏幕；已知屏幕會自動連上");
              });
          button("選擇掃描到的屏幕", () -> selectDevice());
          button(
              "開啟屏幕",
              () ->
                  send(
                      new Intent(this, LedService.class)
                          .setAction(LedService.POWER)
                          .putExtra("on", true)));
          button(
              "關閉屏幕",
              () ->
                  send(
                      new Intent(this, LedService.class)
                          .setAction(LedService.POWER)
                          .putExtra("on", false)));
          button("燈珠全亮測試", () -> send(LedService.TEST));
          text("請先讓 iPhone、Mac、LOY PLAY 斷開屏幕。車機的電話藍牙可用，不代表第三方 App 一定能使用 BLE。", 16);
        });
    addPage(
        content,
        navigation,
        "車況",
        () -> {
          text("車況文字與樣式", 22);
          for (String event : Settings.EVENTS)
            button(Settings.title(event) + " · 編輯", () -> editStyle(event, false, -1));
        });
    addPage(
        content,
        navigation,
        "自訂",
        () -> {
          text("五組自訂文字", 22);
          for (int i = 0; i < 5; i++) {
            final int n = i;
            button("自訂 " + (i + 1) + " · 編輯／顯示", () -> editStyle("slot" + n, true, n));
          }
        });
    addPage(
        content,
        navigation,
        "設定",
        () -> {
          text("像素與字型", 22);
          button("調整屏幕／文字像素", () -> pixels());
          button(
              "匯入中文字型（TTF／OTF）",
              () ->
                  startActivityForResult(
                      new Intent(Intent.ACTION_OPEN_DOCUMENT)
                          .setType("*/*")
                          .addCategory(Intent.CATEGORY_OPENABLE),
                      55));
          button(
              "開啟 App 系統設定",
              () ->
                  startActivity(
                      new Intent(
                          android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                          android.net.Uri.parse("package:" + getPackageName()))));
          text("後窗屏幕仍為 96 × 16，與車機解析度無關。文字動畫為手機逐格傳送；不同系統字型的中文字可能相同，可匯入有授權的中文字型。", 16);
          text(
              "DUDU C3：請在車機的背景／省電管理允許本 App 執行；設定名稱依韌體而異。切換導航不會主動停止本服務，但車機休眠或斷電仍可能中斷；喚醒後請檢查連線。", 16);
          text("每次連動最多 8 小時。藍牙斷線或系統停止時無法保證清屏。請停車設定與測試。", 16);
        });
    selectPage(b == null ? 0 : Math.max(0, Math.min(5, b.getInt("page", 0))));
  }

  final Runnable refresh =
      new Runnable() {
        public void run() {
          syncingAuto = true;
          autoSwitch.setChecked(LedService.automatic);
          syncingAuto = false;
          for (Map.Entry<String, TextView> item : quickLabels.entrySet())
            item.getValue().setText(settings.style(item.getKey()).text);
          state.setText(
              (LedService.running ? "● 背景服務運作中" : "○ 背景服務未啟動")
                  + "\n"
                  + LedService.status
                  + "\n"
                  + LedService.screen
                  + "\n"
                  + LedService.details
                  + "\n"
                  + LedService.previewStatus
                  + "\n目前送出："
                  + LedService.display
                  + "\n自動車況："
                  + (LedService.automatic ? "開" : "關"));
          ui.postDelayed(this, 500);
        }
      };

  protected void onResume() {
    super.onResume();
    ui.post(refresh);
  }

  protected void onPause() {
    ui.removeCallbacks(refresh);
    super.onPause();
  }

  void toast(String s) {
    Toast.makeText(this, s, Toast.LENGTH_LONG).show();
  }

  boolean saveConnection() {
    String address = host.getText().toString().trim(), key = token.getText().toString().trim();
    if (!Settings.privateIP(address)) {
      toast("請輸入 C4 的私人區網 IPv4 位址");
      return false;
    }
    try {
      if (!key.isEmpty()) {
        if (!key.matches("[A-Za-z0-9]{20,128}")) {
          toast("金鑰需 20–128 位英數字，沿用 C4 固定金鑰");
          return false;
        }
        settings.saveToken(key);
        token.setText("");
      } else if (settings.token().isEmpty()) {
        toast("請輸入 C4 橋接金鑰");
        return false;
      }
      settings.p.edit().putString("host", address).apply();
      if (LedService.running) send(LedService.RELOAD);
      ((InputMethodManager) getSystemService(INPUT_METHOD_SERVICE))
          .hideSoftInputFromWindow(host.getWindowToken(), 0);
      toast("連線設定已儲存");
      return true;
    } catch (Exception e) {
      toast("金鑰無法儲存，請重試");
      return false;
    }
  }

  String[] required() {
    ArrayList<String> p = new ArrayList<>();
    if (Build.VERSION.SDK_INT >= 31) {
      p.add(Manifest.permission.BLUETOOTH_SCAN);
      p.add(Manifest.permission.BLUETOOTH_CONNECT);
    } else p.add(Manifest.permission.ACCESS_FINE_LOCATION);
    if (Build.VERSION.SDK_INT >= 33) p.add(Manifest.permission.POST_NOTIFICATIONS);
    return p.toArray(new String[0]);
  }

  boolean permissions() {
    for (String p : required())
      if (checkSelfPermission(p) != PackageManager.PERMISSION_GRANTED) return false;
    return true;
  }

  public void onRequestPermissionsResult(int r, String[] p, int[] g) {
    super.onRequestPermissionsResult(r, p, g);
    if (r == 42) {
      if (permissions()) begin();
      else toast("請允許附近裝置與通知；Android 11 以下另需位置權限才能掃描藍牙");
    }
  }

  void begin() {
    try {
      startForegroundService(new Intent(this, LedService.class).setAction(LedService.START));
    } catch (Exception e) {
      toast("服務無法啟動，請回到 App 後再按開始");
    }
  }

  void send(String action) {
    send(new Intent(this, LedService.class).setAction(action));
  }

  void send(Intent intent) {
    if (!LedService.running) {
      toast("請先開始背景連動");
      return;
    }
    String action = intent.getAction();
    if ((LedService.PREVIEW.equals(action) || LedService.CUSTOM.equals(action))
        && !LedService.connected) {
      toast("請先連接屏幕");
      return;
    }
    if (LedService.CUSTOM.equals(action)
        && settings.style("slot" + intent.getIntExtra("slot", -1)).text.trim().isEmpty()) {
      toast("請先編輯並儲存這組文字");
      return;
    }
    startService(intent);
  }

  void selectDevice() {
    Map<String, String> devices = LedService.discovered;
    if (devices.isEmpty()) {
      toast("尚未找到屏幕，請開啟屏幕並掃描");
      return;
    }
    String[] addresses = devices.keySet().toArray(new String[0]);
    String[] labels = new String[addresses.length];
    for (int i = 0; i < labels.length; i++)
      labels[i] = devices.get(addresses[i]) + "\n" + addresses[i];
    new AlertDialog.Builder(this)
        .setTitle("選擇你的 LOY 屏幕")
        .setItems(
            labels,
            (d, n) ->
                send(
                    new Intent(this, LedService.class)
                        .setAction(LedService.CONNECT)
                        .putExtra("address", addresses[n])))
        .setNegativeButton("取消", null)
        .show();
  }

  LinearLayout column() {
    LinearLayout l = new LinearLayout(this);
    l.setOrientation(LinearLayout.VERTICAL);
    l.setPadding(dp(16), dp(8), dp(16), dp(8));
    return l;
  }

  Spinner spinner(LinearLayout l, String label, String[] options, int selected) {
    TextView t = new TextView(this);
    t.setText(label);
    l.addView(t);
    Spinner s = new Spinner(this);
    s.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, options));
    s.setSelection(Math.max(0, Math.min(selected, options.length - 1)));
    l.addView(s);
    return s;
  }

  void quickRow(String key, String title, Runnable display) {
    LinearLayout row = new LinearLayout(this);
    row.setGravity(Gravity.CENTER_VERTICAL);
    LinearLayout labels = panel();
    TextView heading = new TextView(this);
    heading.setText(title);
    heading.setTextSize(20);
    labels.addView(heading);
    TextView value = new TextView(this);
    value.setTextSize(16);
    labels.addView(value);
    quickLabels.put(key, value);
    row.addView(labels, new LinearLayout.LayoutParams(0, -2, 1));
    Button show = new Button(this);
    show.setText("顯示");
    show.setTextSize(20);
    show.setMinHeight(dp(56));
    show.setOnClickListener(
        v -> {
          hideKeyboard();
          display.run();
        });
    row.addView(show, new LinearLayout.LayoutParams(dp(100), -2));
    body.addView(row);
  }

  void editStyle(String key, boolean custom, int index) {
    Settings.Style old = settings.style(key);
    LinearLayout l = column();
    EditText text = field(l, "顯示文字（最多 16 字，保留空格）", old.text, InputType.TYPE_CLASS_TEXT);
    Spinner effect = spinner(l, "動畫效果", Settings.EFFECTS, old.effect),
        font = spinner(l, "字型", Settings.FONTS, old.font);
    CheckBox bold = new CheckBox(this);
    bold.setText("加粗");
    bold.setChecked(old.bold);
    l.addView(bold);
    int[] color = {old.color};
    Button colorButton = new Button(this);
    colorButton.setText("選擇文字顏色");
    colorButton.setTextColor(old.color);
    colorButton.setOnClickListener(
        v ->
            colorPicker(
                color[0],
                c -> {
                  color[0] = c;
                  colorButton.setTextColor(c);
                }));
    l.addView(colorButton);
    ScrollView sc = new ScrollView(this);
    sc.addView(l);
    AlertDialog.Builder b =
        new AlertDialog.Builder(this)
            .setTitle(custom ? "自訂 " + (index + 1) : Settings.title(key))
            .setView(sc)
            .setNegativeButton("取消", null)
            .setPositiveButton("儲存", null);
    b.setNeutralButton("儲存並顯示", null);
    AlertDialog d = b.create();
    d.setOnShowListener(
        v -> {
          Runnable save =
              () -> {
                String value = text.getText().toString();
                if (value.codePointCount(0, value.length()) > 16
                    || (!custom && value.trim().isEmpty())) {
                  toast("車況文字需 1–16 字，自訂文字最多 16 字");
                  return;
                }
                if (font.getSelectedItemPosition() == 4
                    && !new File(getFilesDir(), "user-font").exists()) {
                  toast("請先匯入中文字型");
                  return;
                }
                settings.save(
                    key,
                    new Settings.Style(
                        value,
                        color[0],
                        effect.getSelectedItemPosition(),
                        font.getSelectedItemPosition(),
                        bold.isChecked()));
                if (LedService.running) send(LedService.RELOAD);
                d.dismiss();
              };
          d.getButton(-1).setOnClickListener(w -> save.run());
          d.getButton(-3)
              .setOnClickListener(
                  w -> {
                    if (text.getText().toString().trim().isEmpty()) {
                      toast("先輸入自訂文字");
                      return;
                    }
                    save.run();
                    if (!d.isShowing())
                      send(
                          new Intent(this, LedService.class)
                              .setAction(custom ? LedService.CUSTOM : LedService.PREVIEW)
                              .putExtra("slot", index)
                              .putExtra("event", key));
                  });
        });
    d.show();
  }

  interface ColorResult {
    void set(int color);
  }

  ScrollView scrollable(View child) {
    ScrollView scroll = new ScrollView(this);
    scroll.addView(child);
    return scroll;
  }

  void colorPicker(int initial, ColorResult result) {
    LinearLayout l = column();
    float[] hsv = new float[3];
    Color.colorToHSV(initial, hsv);
    TextView preview = new TextView(this);
    preview.setText("文字顏色預覽");
    preview.setTextSize(24);
    preview.setTextColor(initial);
    l.addView(preview);
    HueWheel wheel = new HueWheel(this, hsv, () -> preview.setTextColor(Color.HSVToColor(hsv)));
    l.addView(
        wheel,
        new LinearLayout.LayoutParams(
            -1, dp(Math.min(220, getResources().getConfiguration().screenHeightDp / 2))));
    TextView label = new TextView(this);
    label.setText("亮度");
    l.addView(label);
    SeekBar value = new SeekBar(this);
    value.setMax(100);
    value.setProgress((int) (hsv[2] * 100));
    l.addView(value);
    value.setOnSeekBarChangeListener(
        new SeekBar.OnSeekBarChangeListener() {
          public void onProgressChanged(SeekBar b, int p, boolean u) {
            hsv[2] = p / 100f;
            preview.setTextColor(Color.HSVToColor(hsv));
            wheel.invalidate();
          }

          public void onStartTrackingTouch(SeekBar b) {}

          public void onStopTrackingTouch(SeekBar b) {}
        });
    new AlertDialog.Builder(this)
        .setTitle("調色盤")
        .setView(scrollable(l))
        .setPositiveButton("套用", (d, w) -> result.set(Color.HSVToColor(hsv)))
        .setNegativeButton("取消", null)
        .show();
  }

  static final class HueWheel extends View {
    final float[] hsv;
    final Runnable changed;
    final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);

    HueWheel(Context c, float[] h, Runnable change) {
      super(c);
      hsv = h;
      changed = change;
    }

    protected void onDraw(Canvas c) {
      float x = getWidth() / 2f, y = getHeight() / 2f, r = Math.min(x, y) - 16;
      int[] colors = {
        Color.RED, Color.YELLOW, Color.GREEN, Color.CYAN, Color.BLUE, Color.MAGENTA, Color.RED
      };
      p.setShader(new SweepGradient(x, y, colors, null));
      c.drawCircle(x, y, r, p);
      p.setShader(
          new RadialGradient(x, y, r, Color.WHITE, Color.TRANSPARENT, Shader.TileMode.CLAMP));
      c.drawCircle(x, y, r, p);
      p.setShader(null);
      p.setColor(Color.BLACK);
      p.setStyle(Paint.Style.STROKE);
      p.setStrokeWidth(4);
      double angle = Math.toRadians(hsv[0]);
      c.drawCircle(
          x + (float) Math.cos(angle) * r * hsv[1],
          y + (float) Math.sin(angle) * r * hsv[1],
          10,
          p);
      p.setStyle(Paint.Style.FILL);
    }

    public boolean onTouchEvent(android.view.MotionEvent e) {
      if (e.getAction() == MotionEvent.ACTION_DOWN || e.getAction() == MotionEvent.ACTION_MOVE) {
        float x = e.getX() - getWidth() / 2f,
            y = e.getY() - getHeight() / 2f,
            r = Math.min(getWidth(), getHeight()) / 2f - 16;
        hsv[0] = (float) ((Math.toDegrees(Math.atan2(y, x)) + 360) % 360);
        hsv[1] = Math.min(1, (float) Math.hypot(x, y) / r);
        changed.run();
        invalidate();
        return true;
      }
      return true;
    }
  }

  void pixels() {
    LinearLayout l = column();
    EditText w = field(l, "寬（燈珠）", String.valueOf(settings.width()), 2),
        h = field(l, "高（燈珠）", String.valueOf(settings.height()), 2),
        fh = field(l, "文字高度（像素）", String.valueOf(settings.fontHeight()), 2),
        fw = field(l, "文字寬度（%）", String.valueOf(settings.fontWidth()), 2);
    AlertDialog d =
        new AlertDialog.Builder(this)
            .setTitle("屏幕與文字像素")
            .setView(scrollable(l))
            .setPositiveButton("套用", null)
            .setNegativeButton("取消", null)
            .create();
    d.setOnShowListener(
        v ->
            d.getButton(-1)
                .setOnClickListener(
                    b -> {
                      try {
                        int ww = Integer.parseInt(w.getText().toString()),
                            hh = Integer.parseInt(h.getText().toString()),
                            ff = Integer.parseInt(fh.getText().toString()),
                            width = Integer.parseInt(fw.getText().toString());
                        if (ww < 8
                            || ww > 256
                            || hh < 8
                            || hh > 64
                            || ff < 1
                            || ff > hh
                            || width < 50
                            || width > 200) throw new Exception();
                        if (LedService.running) {
                          toast("請先停止背景連動再修改像素，避免新舊尺寸混用");
                          return;
                        }
                        settings
                            .p
                            .edit()
                            .putInt("width", ww)
                            .putInt("height", hh)
                            .putInt("fontHeight", ff)
                            .putInt("fontWidth", width)
                            .apply();
                        d.dismiss();
                      } catch (Exception e) {
                        toast("寬 8–256、高 8–64；字高 1–屏幕高；字寬 50–200%");
                      }
                    }));
    d.show();
  }

  protected void onActivityResult(int request, int result, Intent data) {
    super.onActivityResult(request, result, data);
    if (request != 55 || result != RESULT_OK || data == null) return;
    File temp = new File(getFilesDir(), "font-new");
    try (InputStream in = getContentResolver().openInputStream(data.getData());
        OutputStream out = new FileOutputStream(temp)) {
      byte[] b = new byte[8192];
      int n, total = 0;
      while ((n = in.read(b)) != -1) {
        total += n;
        if (total > 20 * 1024 * 1024) throw new IOException();
        out.write(b, 0, n);
      }
      out.flush();
      Typeface.createFromFile(temp);
      File target = new File(getFilesDir(), "user-font");
      if (!temp.renameTo(target)) throw new IOException();
      toast("字型已匯入，可在各組文字的字型選單選用");
    } catch (Exception e) {
      temp.delete();
      toast("無法匯入，請選有效的 TTF／OTF，最大 20 MB");
    }
  }
}
