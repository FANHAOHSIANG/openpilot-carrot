package tw.carrot.led;
import android.app.*;
import android.content.*;
public final class VehicleNotifications {
  static final String CHANNEL="vehicle_events";
  static void create(Context c) {
    NotificationChannel channel=new NotificationChannel(CHANNEL,"背景車況變更",NotificationManager.IMPORTANCE_HIGH);
    channel.setDescription("App 收到的車況；不是 LED 屏幕回讀");
    c.getSystemService(NotificationManager.class).createNotificationChannel(channel);
  }
  static String status(Context c) {
    NotificationManager n=c.getSystemService(NotificationManager.class);
    if(!n.areNotificationsEnabled()) return "通知權限未開啟";
    NotificationChannel ch=n.getNotificationChannel(CHANNEL);
    if(ch==null) return "通知頻道尚未建立";
    if(ch.getImportance()==NotificationManager.IMPORTANCE_NONE) return "車況通知頻道已關閉";
    if(ch.getImportance()<NotificationManager.IMPORTANCE_HIGH) return "通知列可顯示；請開啟橫幅／浮動通知";
    return "通知已允許；橫幅仍受車機／勿擾／通知冷卻限制";
  }
  static void show(Context c,String title,String detail,int id) {
    create(c);
    if(!c.getSystemService(NotificationManager.class).areNotificationsEnabled()) return;
    PendingIntent open=PendingIntent.getActivity(c,0,new Intent(c,MainActivity.class),PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
    c.getSystemService(NotificationManager.class).notify(id,new Notification.Builder(c,CHANNEL)
      .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth).setContentTitle(title).setContentText(detail)
      .setContentIntent(open).setAutoCancel(true).setTimeoutAfter(6000).build());
  }
}
