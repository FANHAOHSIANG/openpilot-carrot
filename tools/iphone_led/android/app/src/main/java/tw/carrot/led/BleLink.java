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
  final boolean ipixel;
  boolean awaitingAck = false, ackSeen = false, finalAckRequired = false;
  long ackGeneration = 0;
  final ArrayDeque<byte[]> packets = new ArrayDeque<>();
  String deviceKey() { return ipixel ? "ipixelDevice" : "device"; }
  int writeType() { return ipixel ? BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT : BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE; }
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
    ipixel = s.ipixel();
  }

  BluetoothAdapter adapter() {
    return context.getSystemService(BluetoothManager.class).getAdapter();
  }

  void start() {
    closed = false;
    String address = settings.p.getString(deviceKey(), "");
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
      status = ipixel ? "掃描 iPixel；請讓原廠 App 先斷線" : "掃描 LOY 屏幕；請讓 iPhone／LOY PLAY 先斷線";
      scanner.startScan(
          ipixel ? Collections.emptyList() : Collections.singletonList(
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
                if (name == null) name = "未命名藍牙設備";

                String address = r.getDevice().getAddress();
                devices.put(address, name);
                if (!ipixel && name.equals("YS5255140425")) connect(address);
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
                  if (!g.requestMtu(ipixel ? 247 : 185)) discover(g);
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
                if (ipixel) { svc = null; for (BluetoothGattService candidate : g.getServices())
                  if (candidate.getCharacteristic(uuid("fa02")) != null && candidate.getCharacteristic(uuid("fa03")) != null) { svc=candidate;break; } }
                if (code != 0 || svc == null) {
                  fail(ipixel ? "找不到 iPixel FA02/FA03 通道，請確認屏幕類型" : "找不到 LOY FFF0 通道");
                  return;
                }
                writer = svc.getCharacteristic(uuid(ipixel?"fa02":"fff2"));
                BluetoothGattCharacteristic notify = svc.getCharacteristic(uuid(ipixel?"fa03":"fff1"));
                if (writer == null
                    || notify == null
                    || (writer.getProperties()
                            & (ipixel ? BluetoothGattCharacteristic.PROPERTY_WRITE : BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE))
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
                settings.p.edit().putString(deviceKey(), g.getDevice().getAddress()).apply();
                status = (ipixel ? "iPixel" : "LOY") + " 藍牙已連線（尚非畫面回讀確認）";
                onReady.run();
              });
        }

        public void onCharacteristicChanged(BluetoothGatt g, BluetoothGattCharacteristic c) {
          received(g, c, c.getValue());
        }
        public void onCharacteristicChanged(BluetoothGatt g, BluetoothGattCharacteristic c, byte[] value) {
          received(g, c, value);
        }
        private void received(BluetoothGatt g, BluetoothGattCharacteristic c, byte[] value) {
          byte[] copy = value == null ? null : value.clone();
          h.post(() -> {
            if (g != gatt || !ipixel || !c.getUuid().equals(uuid("fa03")) || !awaitingAck) return;
            if (IPixelProtocol.ack(copy) && (!finalAckRequired || copy[4] == 3)) { ackSeen = true; status = "iPixel 已回覆接收（非畫面回讀）"; pump(); }
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
                // With-response writes already provide backpressure. Avoid a second artificial delay for GIFs.
                h.postDelayed(() -> pump(), ipixel ? 0 : 20);
              });
        }
      };

  void controls(List<byte[]> commands) {
    if (!ready) return;
    pending=null; packets.clear(); packets.addAll(commands); pump();
  }

  void offer(List<byte[]> commands) {
    if (!ready) return;
    pending = commands;
    pump();
  }

  void pump() {
    if (!ready || writing || closed) return;
    if (chunks.isEmpty() && awaitingAck) {
      if (!ackSeen) return;
      awaitingAck=false; ackSeen=false; ackGeneration++;
    }
    if (chunks.isEmpty() && packets.isEmpty() && pending != null) {
      packets.addAll(pending); pending=null;
    }
    if (chunks.isEmpty() && !packets.isEmpty()) {
      byte[] command=packets.removeFirst();
      byte[] frame=ipixel ? command : protocol.frame(command);
      int limit=Math.max(20,Math.min(ipixel?244:180,mtu-3));
      for (int i=0;i<frame.length;i+=limit) chunks.add(Arrays.copyOfRange(frame,i,Math.min(frame.length,i+limit)));
      if (ipixel) {
        awaitingAck=true;ackSeen=false;finalAckRequired=command.length>5;long ticket=++ackGeneration;
        h.postDelayed(() -> { if (awaitingAck && ackGeneration==ticket) fail("iPixel 接收回覆逾時，重新連接；請確認屏幕畫面"); },15000);
      }
    }
    if (chunks.isEmpty()) return;
    writer.setWriteType(writeType());
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
    return !writing && !awaitingAck && chunks.isEmpty() && packets.isEmpty() && pending == null;
  }
  boolean nativeEyesReady(){return ipixel && mtu-3>=100;}

  void fail(String text) {
    status = text;
    drop();
    retry();
  }

  void drop() {
    ready = false;
    writer = null;
    writing = false;
    chunks.clear(); packets.clear(); awaitingAck=false; ackSeen=false; ackGeneration++;
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
