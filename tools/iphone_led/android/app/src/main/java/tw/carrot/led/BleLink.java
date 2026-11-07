package tw.carrot.led;

import android.annotation.SuppressLint;
import android.bluetooth.*;
import android.bluetooth.le.*;
import android.content.Context;
import android.os.*;
import java.util.*;

@SuppressLint("MissingPermission")
final class BleLink {
  static UUID uuid(String shortID) {
    return UUID.fromString("0000" + shortID + "-0000-1000-8000-00805f9b34fb");
  }

  final Context context;
  final Handler h;
  final Settings settings;
  final Map<String, String> devices = new LinkedHashMap<>();
  String status = "尚未連線";
  boolean ready = false, closed = false, scanning = false;
  BluetoothGatt gatt;
  BluetoothGattCharacteristic writer;
  BluetoothLeScanner scanner;
  int mtu = 23;
  boolean discovering = false, writing = false;
  long lastWrite = 0;
  final ArrayDeque<byte[]> chunks = new ArrayDeque<>();
  List<byte[]> pending;
  final LoyProtocol protocol = new LoyProtocol();
  Runnable onReady = () -> {};

  BleLink(Context c, Handler handler, Settings s) {
    context = c;
    h = handler;
    settings = s;
  }

  BluetoothAdapter adapter() {
    return context.getSystemService(BluetoothManager.class).getAdapter();
  }

  void start() {
    closed = false;
    String address = settings.p.getString("device", "");
    if (BluetoothAdapter.checkBluetoothAddress(address)) connect(address);
    else scan();
  }

  void scan() {
    if (closed) return;
    try {
      BluetoothAdapter a = adapter();
      if (a == null || !a.isEnabled()) {
        status = "請開啟藍牙";
        retry();
        return;
      }
      stopScan();
      devices.clear();
      scanner = a.getBluetoothLeScanner();
      scanning = true;
      status = "掃描 LOY 屏幕；請讓 iPhone／LOY PLAY 先斷線";
      scanner.startScan(
          Collections.singletonList(
              new ScanFilter.Builder().setServiceUuid(new ParcelUuid(uuid("fff0"))).build()),
          new ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build(),
          scanCallback);
      h.postDelayed(
          () -> {
            if (scanning) {
              stopScan();
              status = "掃描結束，請選擇屏幕或重新掃描";
              retry();
            }
          },
          12000);
    } catch (Exception e) {
      status = "藍牙權限或掃描不可用";
      retry();
    }
  }

  void stopScan() {
    if (scanning && scanner != null) {
      try {
        scanner.stopScan(scanCallback);
      } catch (Exception ignored) {
      }
    }
    scanning = false;
  }

  final ScanCallback scanCallback =
      new ScanCallback() {
        public void onScanResult(int type, ScanResult r) {
          h.post(
              () -> {
                if (closed || !scanning) return;
                String name = r.getScanRecord() != null ? r.getScanRecord().getDeviceName() : null;
                if (name == null) name = "LOY 屏幕";
                String address = r.getDevice().getAddress();
                devices.put(address, name);
                if (name.equals("YS5255140425")) connect(address);
              });
        }

        public void onScanFailed(int error) {
          h.post(
              () -> {
                scanning = false;
                status = "掃描失敗：" + error;
                retry();
              });
        }
      };

  void retry() {
    h.postDelayed(
        () -> {
          if (!closed && gatt == null && !scanning) start();
        },
        5000);
  }

  void connect(String address) {
    if (closed) return;
    stopScan();
    drop();
    try {
      BluetoothAdapter a = adapter();
      if (a == null || !a.isEnabled()) {
        status = "請開啟藍牙";
        retry();
        return;
      }
      status = "正在連接屏幕";
      gatt =
          a.getRemoteDevice(address)
              .connectGatt(context, false, callback, BluetoothDevice.TRANSPORT_LE);
      BluetoothGatt attempt = gatt;
      h.postDelayed(
          () -> {
            if (!closed && gatt == attempt && !ready) fail("屏幕握手逾時");
          },
          15000);
    } catch (Exception e) {
      fail("屏幕連線失敗");
    }
  }

  void discover(BluetoothGatt g) {
    if (g != gatt || discovering) return;
    discovering = true;
    if (!g.discoverServices()) fail("無法探索屏幕通道");
  }

  final BluetoothGattCallback callback =
      new BluetoothGattCallback() {
        public void onConnectionStateChange(BluetoothGatt g, int statusCode, int newState) {
          h.post(
              () -> {
                if (g != gatt) return;
                if (statusCode != 0 || newState == BluetoothProfile.STATE_DISCONNECTED) {
                  fail("屏幕已斷線；可能保留舊畫面");
                  return;
                }
                if (newState == BluetoothProfile.STATE_CONNECTED) {
                  if (!g.requestMtu(185)) discover(g);
                  h.postDelayed(() -> discover(g), 2000);
                }
              });
        }

        public void onMtuChanged(BluetoothGatt g, int value, int code) {
          h.post(
              () -> {
                if (g != gatt) return;
                if (code == 0) mtu = value;
                discover(g);
              });
        }

        public void onServicesDiscovered(BluetoothGatt g, int code) {
          h.post(
              () -> {
                if (g != gatt) return;
                BluetoothGattService svc = g.getService(uuid("fff0"));
                if (code != 0 || svc == null) {
                  fail("找不到 LOY FFF0 通道");
                  return;
                }
                writer = svc.getCharacteristic(uuid("fff2"));
                BluetoothGattCharacteristic notify = svc.getCharacteristic(uuid("fff1"));
                if (writer == null
                    || notify == null
                    || (writer.getProperties()
                            & BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE)
                        == 0
                    || (notify.getProperties() & BluetoothGattCharacteristic.PROPERTY_NOTIFY)
                        == 0) {
                  fail("屏幕通道不相容");
                  return;
                }
                BluetoothGattDescriptor d = notify.getDescriptor(uuid("2902"));
                if (d == null || !g.setCharacteristicNotification(notify, true)) {
                  fail("無法啟用屏幕通知");
                  return;
                }
                d.setValue(BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
                if (!g.writeDescriptor(d)) fail("通知訂閱失敗");
              });
        }

        public void onDescriptorWrite(BluetoothGatt g, BluetoothGattDescriptor d, int code) {
          h.post(
              () -> {
                if (g != gatt) return;
                if (code != 0) {
                  fail("屏幕通知確認失敗");
                  return;
                }
                ready = true;
                settings.p.edit().putString("device", g.getDevice().getAddress()).apply();
                status = "屏幕藍牙已連線（尚非畫面回讀確認）";
                onReady.run();
              });
        }

        public void onCharacteristicWrite(
            BluetoothGatt g, BluetoothGattCharacteristic c, int code) {
          h.post(
              () -> {
                if (g != gatt || !writing) return;
                if (code != 0) {
                  fail("藍牙傳送失敗");
                  return;
                }
                writing = false;
                h.postDelayed(() -> pump(), 20);
              });
        }
      };

  void offer(List<byte[]> commands) {
    if (!ready) return;
    pending = commands;
    pump();
  }

  void pump() {
    if (!ready || writing || closed) return;
    if (chunks.isEmpty() && pending != null) {
      List<byte[]> next = pending;
      pending = null;
      for (byte[] command : next) {
        byte[] frame = protocol.frame(command);
        int limit = Math.max(20, Math.min(180, mtu - 3));
        for (int i = 0; i < frame.length; i += limit)
          chunks.add(Arrays.copyOfRange(frame, i, Math.min(frame.length, i + limit)));
      }
    }
    if (chunks.isEmpty()) return;
    writer.setWriteType(BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE);
    writer.setValue(chunks.removeFirst());
    writing = true;
    lastWrite = SystemClock.elapsedRealtime();
    long started = lastWrite;
    if (!gatt.writeCharacteristic(writer)) {
      writing = false;
      fail("屏幕傳送忙碌，重新連接");
      return;
    }
    h.postDelayed(
        () -> {
          if (writing && lastWrite == started) fail("藍牙寫入逾時");
        },
        3000);
  }

  boolean idle() {
    return !writing && chunks.isEmpty() && pending == null;
  }

  void fail(String text) {
    status = text;
    drop();
    retry();
  }

  void drop() {
    ready = false;
    writer = null;
    writing = false;
    chunks.clear();
    pending = null;
    mtu = 23;
    discovering = false;
    BluetoothGatt old = gatt;
    gatt = null;
    if (old != null) {
      try {
        old.disconnect();
        old.close();
      } catch (Exception ignored) {
      }
    }
  }

  void close() {
    closed = true;
    stopScan();
    drop();
  }
}
