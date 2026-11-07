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
    if(index==0 && quickArea!=null)populateQuick();
    for (int i = 0; i < pages.size(); i++) {
      pages.get(i).setVisibility(i == index ? View.VISIBLE : View.GONE);
      tabs.get(i).setTextColor(i == index ? ACCENT : MUTED);
      tabs.get(i).setBackground(rounded(i==index?SURFACE:BG,i==index?LINE:BG,12));
    }
  }

  void addPage(LinearLayout content, LinearLayout navigation, String title, Runnable populate) {
    int index = pages.size();
    Button tab = new Button(this);
    tab.setText(title);
    styleButton(tab,false);
    tab.setTextSize(15);
    tab.setMinHeight(dp(52));
    tab.setOnClickListener(v -> selectPage(index));
    navigation.addView(tab, new LinearLayout.LayoutParams(0, dp(56),1));
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
      selectPage(2);
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
    v.setTextColor(size>=20?INK:MUTED);
    if(size>=20)v.setTypeface(null,Typeface.BOLD);
    v.setPadding(0, dp(12), 0, dp(6));
    body.addView(v);
  }

  Button button(String s, Runnable action) {
    Button b = new Button(this);
    b.setText(s);
    b.setAllCaps(false);
    styleButton(b,false);
    b.setTextSize(17);
    b.setMinHeight(dp(56));
    b.setOnClickListener(v -> action.run());
    block(b,body,-2);
    return b;
  }

  EditText field(LinearLayout box, String hint, String value, int type) {
    EditText e = new EditText(this);
    e.setHint(hint);
    e.setText(value);
    e.setInputType(type);
    e.setSingleLine(true);
    e.setMinHeight(dp(56));
    e.setTextSize(17);
    e.setTextColor(INK);e.setHintTextColor(MUTED);
    e.setBackgroundTintList(android.content.res.ColorStateList.valueOf(ACCENT));
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

  static final int BG=0xff0b0f14, SURFACE=0xff151b24, LINE=0xff293340, INK=0xfff1f4f8,
      MUTED=0xff9ca9b9, ACCENT=0xffffb347, GREEN=0xff55e6a5;
  TextView previewLabel,c4Pill,screenPill,backgroundPill;
  Button powerButton,sessionButton;
  LinearLayout quickArea;
  final ArrayList<View> quickTiles=new ArrayList<>();
  final ArrayList<Button> quickGroupButtons=new ArrayList<>();
  int quickGroup=0;
  boolean wide;

  android.graphics.drawable.GradientDrawable rounded(int fill,int stroke,int radius) {
    android.graphics.drawable.GradientDrawable d=new android.graphics.drawable.GradientDrawable();
    d.setColor(fill); d.setCornerRadius(dp(radius));d.setStroke(dp(1),stroke);return d;
  }
  void styleButton(Button b,boolean primary) {
    b.setAllCaps(false);b.setTextSize(16);b.setTextColor(primary?BG:INK);
    b.setMinHeight(dp(54));b.setPadding(dp(14),dp(10),dp(14),dp(10));
    b.setBackgroundTintList(null);
    b.setBackground(new android.graphics.drawable.RippleDrawable(
      android.content.res.ColorStateList.valueOf(0x33ffffff),rounded(primary?ACCENT:SURFACE,primary?ACCENT:LINE,14),null));
  }
  TextView label(String title,int size,int color) {
    TextView t=new TextView(this);t.setText(title);t.setTextSize(size);t.setTextColor(color);return t;
  }
  void block(View view,LinearLayout parent,int height) {
    LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,height);lp.bottomMargin=dp(12);parent.addView(view,lp);
  }
  TextView pill(String title) {
    TextView t=label(title,12,MUTED);t.setPadding(dp(10),dp(8),dp(10),dp(8));t.setBackground(rounded(SURFACE,LINE,24));return t;
  }
  void dashboard(LinearLayout target) {
    LinearLayout previous=body;body=target;
    TextView brand=label("CARROT / LED",12,ACCENT);brand.setLetterSpacing(.22f);block(brand,body,-2);
    TextView title=label("讓後車看見",26,INK);title.setTypeface(null,Typeface.BOLD);block(title,body,-2);
    LinearLayout statusRow=new LinearLayout(this);
    c4Pill=pill("● C4 等待中");screenPill=pill("● 屏幕未連線");backgroundPill=pill("● 背景待命");
    for(TextView t:new TextView[]{c4Pill,screenPill,backgroundPill}){
      LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,-2,1);lp.rightMargin=dp(4);statusRow.addView(t,lp);
    }
    block(statusRow,body,-2);
    LinearLayout preview=column();preview.setPadding(dp(20),dp(16),dp(20),dp(16));preview.setBackground(rounded(SURFACE,ACCENT,22));
    preview.addView(label("目前送出   /   APP DISPLAY",12,MUTED));
    previewLabel=label("清屏",32,ACCENT);previewLabel.setTypeface(null,Typeface.BOLD);previewLabel.setMinHeight(dp(72));previewLabel.setGravity(Gravity.CENTER_VERTICAL);previewLabel.setMaxLines(2);
    preview.addView(previewLabel,new LinearLayout.LayoutParams(-1,-2));
    preview.addView(label("依 App 指令顯示，非屏幕畫面回讀",11,MUTED));block(preview,body,-2);
    LinearLayout actions=new LinearLayout(this);
    powerButton=new Button(this);styleButton(powerButton,false);powerButton.setText("⏻\n已關閉");
    powerButton.setOnClickListener(v->send(new Intent(this,LedService.class).setAction(LedService.POWER).putExtra("on",!LedService.powerOn)));
    LinearLayout.LayoutParams powerLP=new LinearLayout.LayoutParams(dp(88),dp(78));powerLP.rightMargin=dp(12);actions.addView(powerButton,powerLP);
    Button clear=new Button(this);styleButton(clear,false);clear.setText("▣  清除屏幕\n停止文字、動畫與連動");clear.setTextColor(0xffff8b7e);clear.setBackground(rounded(0xff3d1a1c,0xff70403d,18));clear.setOnClickListener(v->send(LedService.CLEAR));actions.addView(clear,new LinearLayout.LayoutParams(0,dp(78),1));block(actions,body,-2);
    autoSwitch=new Switch(this);autoSwitch.setText("自動車況");autoSwitch.setTextColor(INK);autoSwitch.setTextSize(18);autoSwitch.setPadding(dp(16),dp(6),dp(16),dp(6));autoSwitch.setMinHeight(dp(60));autoSwitch.setBackground(rounded(SURFACE,LINE,16));
    autoSwitch.setOnCheckedChangeListener((v,checked)->{if(!syncingAuto)send(new Intent(this,LedService.class).setAction(LedService.AUTO).putExtra("enabled",checked));});block(autoSwitch,body,-2);
    body=previous;
  }
  void makeQuickPage() {
    if(!wide)dashboard(body);
    LinearLayout groups=new LinearLayout(this);
    for(int i=0;i<3;i++) {final int index=i;Button tab=new Button(this);styleButton(tab,false);tab.setText(new String[]{"車況","自訂文字","眼睛動畫"}[i]);
      quickGroupButtons.add(tab);tab.setOnClickListener(v->{quickGroup=index;populateQuick();});groups.addView(tab,new LinearLayout.LayoutParams(0,dp(50),1));}
    block(groups,body,-2);
    quickArea=new LinearLayout(this);quickArea.setOrientation(LinearLayout.VERTICAL);body.addView(quickArea);populateQuick();
    text("車況預覽 5 秒後恢復原模式。眼睛及自訂文字會讓車況優先。請停車設定。",13);
  }
  String icon(String key) {
    if(key.equals("倒車"))return "↶";if(key.equals("左轉彎"))return "←";if(key.equals("右轉彎"))return "→";
    if(key.equals("減速中"))return "■";if(key.equals("暫停一下謝謝"))return "Ⅱ";if(key.equals("謝謝"))return "♥";if(key.equals("前方塞車"))return "⚠";return "▤";
  }
  void populateQuick() {
    if(quickArea==null)return;for(int n=0;n<quickGroupButtons.size();n++){Button b=quickGroupButtons.get(n);b.setTextColor(n==quickGroup?ACCENT:MUTED);b.setBackground(rounded(SURFACE,n==quickGroup?ACCENT:LINE,12));}quickArea.removeAllViews();quickLabels.clear();quickTiles.clear();
    int available=wide?(int)(getResources().getConfiguration().screenWidthDp*.66f)-48:getResources().getConfiguration().screenWidthDp-40;
    int columns=Math.max(2,Math.min(4,available/145));
    int count=quickGroup==0?7:quickGroup==1?5:3;
    LinearLayout row=null;
    for(int i=0;i<count;i++) {
      if(i%columns==0){row=new LinearLayout(this);block(row,quickArea,-2);}
      final int index=i;String key=quickGroup==0?Settings.EVENTS[i]:"slot"+i;
      LinearLayout tile=column();tile.setPadding(dp(16),dp(16),dp(16),dp(16));tile.setGravity(Gravity.TOP);tile.setMinimumHeight(dp(148));
      tile.setBackground(new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(0x33ffffff),rounded(SURFACE,LINE,18),null));
      String title;
      if(quickGroup==2) {
        EyeThumb eyes=new EyeThumb(this,i);tile.addView(eyes,new LinearLayout.LayoutParams(-1,dp(40)));title=new String[]{"眨眨眼","左右看","惡魔眼"}[i];
      } else {TextView symbol=label(icon(key),29,quickGroup==0?ACCENT:settings.style(key).color);tile.addView(symbol);title=quickGroup==0?Settings.title(key):"自訂 "+(i+1);}
      TextView heading=label(title,18,INK);heading.setTypeface(null,Typeface.BOLD);heading.setPadding(0,dp(10),0,dp(7));tile.addView(heading);
      TextView value=label(quickGroup==2?"點一下顯示":settings.style(key).text,14,MUTED);value.setMaxLines(2);tile.addView(value);
      if(quickGroup!=2)quickLabels.put(key,value);
      final int group=quickGroup;
      tile.setOnClickListener(v->{hideKeyboard();if(group==2){settings.p.edit().putInt("eyes.variant",index).apply();send(LedService.EYES);}else send(new Intent(this,LedService.class).setAction(group==0?LedService.PREVIEW:LedService.CUSTOM).putExtra("event",key).putExtra("slot",index));});
      tile.setFocusable(true);tile.setContentDescription("顯示 "+title);quickTiles.add(tile);
      LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,-1,1);if(i%columns<columns-1)lp.rightMargin=dp(12);row.addView(tile,lp);
      if(i==count-1)for(int blank=i%columns+1;blank<columns;blank++){View spacer=new View(this);row.addView(spacer,new LinearLayout.LayoutParams(0,dp(148),1));}
    }
  }
  final class EyeThumb extends View {
    final int variant;final Paint paint=new Paint();EyeThumb(Context c,int v){super(c);variant=v;}
    protected void onDraw(Canvas c){byte[] bits=EyesBitmap.make(64,16,variant,0);float step=Math.min(getWidth()/64f,getHeight()/16f);paint.setColor(settings.p.getInt("eyes.color",0xff00dcc8));
      for(int y=0;y<16;y++)for(int x=0;x<64;x++)if((bits[y*8+x/8]&(128>>(x%8)))!=0)c.drawRect(x*step,y*step,(x+1)*step-.5f,(y+1)*step-.5f,paint);}
  }
  void autoStartIfReady() {
    if(LedService.running || !settings.p.getBoolean("autoLaunch",true))return;
    try {if(Settings.privateIP(settings.host()) && !settings.token().isEmpty()){
      if(permissions())begin();else requestPermissions(required(),42);
    }}catch(Exception ignored){}
  }
  public void onCreate(Bundle b) {
    super.onCreate(b);settings=new Settings(this);
    wide=getResources().getConfiguration().screenWidthDp>=700 && getResources().getConfiguration().screenWidthDp>getResources().getConfiguration().screenHeightDp;
    getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);
    LinearLayout root=new LinearLayout(this);root.setOrientation(wide?LinearLayout.HORIZONTAL:LinearLayout.VERTICAL);root.setBackgroundColor(BG);setContentView(root);
    root.setOnApplyWindowInsetsListener((v,insets)->{
      if(Build.VERSION.SDK_INT>=30){android.graphics.Insets bars=insets.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout());android.graphics.Insets ime=insets.getInsets(WindowInsets.Type.ime());v.setPadding(bars.left,bars.top,bars.right,Math.max(bars.bottom,ime.bottom));}
      else v.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());return insets;});root.requestApplyInsets();
    if(wide){ScrollView sidebar=new ScrollView(this);LinearLayout left=panel();sidebar.addView(left);dashboard(left);root.addView(sidebar,new LinearLayout.LayoutParams(0,-1,.34f));}
    LinearLayout editor=panel();root.addView(editor,wide?new LinearLayout.LayoutParams(0,-1,.66f):new LinearLayout.LayoutParams(-1,-1));
    LinearLayout content=new LinearLayout(this);content.setOrientation(LinearLayout.VERTICAL);editor.addView(content,new LinearLayout.LayoutParams(-1,0,1));
    LinearLayout navigation=new LinearLayout(this);navigation.setPadding(0,dp(8),0,0);editor.addView(navigation,new LinearLayout.LayoutParams(-1,dp(66)));
    addPage(content,navigation,"▦ 快捷",()->makeQuickPage());
    addPage(content,navigation,"文字動畫",()->{
      text("文字與動畫",26);text("每個項目獨立儲存，點選即可編輯。",14);
      text("車況文字",20);for(String event:Settings.EVENTS)button(icon(event)+"  "+Settings.title(event),()->editStyle(event,false,-1));
      text("五組自訂文字",20);for(int i=0;i<5;i++){final int n=i;button("自訂 "+(i+1)+" · 編輯與顯示",()->editStyle("slot"+n,true,n));}
      text("眼睛動畫",20);button("選擇眼睛顏色",()->colorPicker(settings.p.getInt("eyes.color",0xff00dcc8),c->{settings.p.edit().putInt("eyes.color",c).apply();populateQuick();if(LedService.running)send(LedService.RELOAD);}));
      text("三種原創點陣動畫：眨眼、左右看、惡魔眼。車況提示優先，清屏會停止動畫。",14);
    });
    addPage(content,navigation,"連線設定",()->{
      text("連線設定",26);text("C4 車況橋接",20);
      host=field(body,"C4 區網 IP",b==null?settings.host():b.getString("hostDraft",settings.host()),InputType.TYPE_CLASS_PHONE);
      token=field(body,"橋接金鑰（已儲存可留空）","",InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);token.setSaveEnabled(false);
      button("儲存連線設定",()->{if(saveConnection())autoStartIfReady();});
      state=label("等待連線",14,MUTED);state.setPadding(0,dp(8),0,dp(8));body.addView(state);
      sessionButton=button("開始背景連動",()->{if(LedService.running)send(LedService.STOP);else startSession();});
      Switch launch=new Switch(this);launch.setText("開啟 App 自動開始連動");launch.setTextColor(INK);launch.setMinHeight(dp(56));launch.setChecked(settings.p.getBoolean("autoLaunch",true));launch.setOnCheckedChangeListener((v,value)->settings.p.edit().putBoolean("autoLaunch",value).apply());body.addView(launch);
      text("已有連線設定及授權時自動啟動；首次請輸入 IP 與金鑰。這不是車機開機自啟。",14);
      text("LED 屏幕",20);
      button("屏幕類型 · LOY / iPixel Color",()->{
        if(LedService.running){toast("請先停止背景連動再切換屏幕類型");return;}
        new AlertDialog.Builder(this).setTitle("選擇屏幕類型").setSingleChoiceItems(new String[]{"LOY PLAY · 96 × 16","iPixel Color · 64 × 16"},settings.ipixel()?1:0,(dialog,which)->{boolean ip=which==1;settings.p.edit().putBoolean("ipixel",ip).putInt("width",ip?64:96).putInt("height",16).putInt("fontHeight",16).apply();dialog.dismiss();toast("類型已儲存，請重新開始背景連動");}).setNegativeButton("取消",null).show();});
      button("掃描屏幕",()->{send(LedService.SCAN);toast("掃描約 12 秒，再按選擇屏幕");});button("選擇掃描到的屏幕",()->selectDevice());button("燈珠全亮測試",()->send(LedService.TEST));
      text("先讓 iPixel Color／LOY PLAY 與其他裝置斷開屏幕。",14);
      text("像素與字型",20);button("調整屏幕／文字像素",()->pixels());button("匯入中文字型 TTF / OTF",()->startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE),55));
      button("App 系統與背景權限",()->startActivity(new Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS,android.net.Uri.parse("package:"+getPackageName()))));
      text("DUDU 車機請允許背景執行。每次連動最多 8 小時，休眠或強制停止後請重新確認連線。",14);
      text("Carrot LED 0.1.4 · Android "+Build.VERSION.RELEASE,13);
    });
    selectPage(b==null?0:Math.max(0,Math.min(2,b.getInt("page",0))));
    ui.post(()->autoStartIfReady());
  }

  final Runnable refresh =
      new Runnable() {
        public void run() {
          syncingAuto = true;
          autoSwitch.setChecked(LedService.automatic);
          syncingAuto = false;
          for (Map.Entry<String, TextView> item : quickLabels.entrySet())
            item.getValue().setText(settings.style(item.getKey()).text);
          state.setText(LedService.status+"\n"+LedService.screen+"\n"+LedService.details+"\n"+LedService.previewStatus);
          previewLabel.setText(LedService.display);
          c4Pill.setText(LedService.status.equals("已收到 C4 車況")?"● C4 已連線":"● C4 等待中");
          c4Pill.setTextColor(LedService.status.equals("已收到 C4 車況")?GREEN:MUTED);
          screenPill.setText(LedService.connected?"● 屏幕已連線":"● 屏幕未連線");screenPill.setTextColor(LedService.connected?GREEN:MUTED);
          backgroundPill.setText(LedService.running?"● 背景運作":"● 背景待命");backgroundPill.setTextColor(LedService.running?GREEN:MUTED);
          boolean on=LedService.connected&&LedService.powerOn;
          powerButton.setText(!LedService.connected?"⏻\n未連線":on?"⏻\n已開啟":"⏻\n已關閉");powerButton.setTextColor(on?GREEN:MUTED);
          powerButton.setBackground(rounded(on?0xff102e26:Color.BLACK,on?GREEN:LINE,18));powerButton.setEnabled(LedService.connected);
          sessionButton.setText(LedService.running?"停止背景連動":"開始背景連動");
          for(View tile:quickTiles){tile.setEnabled(LedService.connected);tile.setAlpha(LedService.connected?1f:.55f);}
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
    if ((LedService.PREVIEW.equals(action) || LedService.CUSTOM.equals(action) || LedService.EYES.equals(action))
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
        .setTitle(settings.ipixel() ? "選擇你的 iPixel 屏幕" : "選擇你的 LOY 屏幕")
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
                        if (settings.ipixel() && hh != 16) { toast("iPixel 此版需設定 16 排，這款請用 64 × 16"); return; }
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
