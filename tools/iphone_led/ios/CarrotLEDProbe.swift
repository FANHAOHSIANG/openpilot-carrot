import SwiftUI
import UIKit
import CoreBluetooth
import Security

@main
struct CarrotLEDProbeApp: App {
    @StateObject private var model = CarrotLED()
    @Environment(\.scenePhase) private var scenePhase
    var body: some Scene {
        WindowGroup {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Text("C4 → iPhone → 後窗 LED").font(.title2.bold())
                    Text("先在 C4 啟動唯讀車況橋接，iPhone 與 C4 接入同一區網。")
                    TextField("C4 的 IP", text: $model.host).textInputAutocapitalization(.never).autocorrectionDisabled().textFieldStyle(.roundedBorder)
                    SecureField("橋接連線金鑰", text: $model.token).textInputAutocapitalization(.never).autocorrectionDisabled().textFieldStyle(.roundedBorder)
                    HStack {
                        Button("連接 C4") { model.connectC4() }
                        Button("斷開 C4") { model.disconnectC4() }
                    }
                    Text(model.vehicleStatus)
                    Text(model.values).font(.system(.caption, design: .monospaced))
                    Divider()
                    Button("掃描並連接屏幕") { model.scan() }
                    Text(model.bluetoothStatus)
                    HStack {
                        Button("開啟屏幕") { model.power(true) }.disabled(!model.ready)
                        Button("關閉屏幕") { model.power(false) }.disabled(!model.ready)
                    }
                    Toggle("自動顯示車況", isOn: $model.enabled)
                    Text("目前提示：\(model.currentLabel)")
                    Divider()
                    Text("五組自訂文字").font(.headline)
                    ForEach(0..<5, id: \.self) { index in
                        VStack(alignment: .leading) {
                            Text("自訂 \(index + 1)")
                            TextField("文字，最多 16 字", text: $model.customSlots[index].text)
                                .textFieldStyle(.roundedBorder)
                            HStack {
                                TextField("顏色 RRGGBB", text: $model.customSlots[index].color)
                                    .textInputAutocapitalization(.characters).autocorrectionDisabled()
                                    .textFieldStyle(.roundedBorder)
                                Picker("效果", selection: $model.customSlots[index].effect) {
                                    Text("靜態").tag("static"); Text("閃爍").tag("blink")
                                    Text("左跑馬燈").tag("left"); Text("右跑馬燈").tag("right")
                                    Text("呼吸").tag("breathe"); Text("自動換色").tag("rainbow")
                                    Text("向左動態箭頭").tag("arrowsLeft"); Text("向右動態箭頭").tag("arrowsRight")
                                    Text("波浪圖案").tag("wave"); Text("愛心圖案").tag("heart")
                                    Text("警示圖案").tag("warning")
                                }
                            }
                            HStack {
                                Picker("字重", selection: $model.customSlots[index].bold) {
                                    Text("一般").tag(false); Text("加粗").tag(true)
                                }.pickerStyle(.segmented)
                                Button("儲存") { model.saveSlots() }
                                Button("顯示") { model.activateSlot(index) }
                            }
                        }.padding(.vertical, 5)
                    }
                    Button("清除自訂文字") { model.clearSlot() }
                    Text(model.customStatus).font(.footnote)
                    Text("預設 96 × 16。已加入自動連線與背景藍牙；iOS 可能暫停背景車況接收，請先停車實測。")
                        .font(.footnote).foregroundStyle(.secondary)
                }.padding()
            }
            .onChange(of: scenePhase) { phase in
                if phase == .active { model.returnToForeground() }
                if phase == .background { model.enterBackground() }
            }
        }
    }
}

struct CustomSlot: Codable {
    var text = ""
    var color = "FFB400"
    var effect = "static"
    var bold = false
}

private struct CarState: Decodable {
    let valid: Bool
    let speed: Double?
    let accel: Double?
    let brake: Bool?
    let left: Bool?
    let right: Bool?
    let gear: String?
}

@MainActor
final class CarrotLED: NSObject, ObservableObject, CBCentralManagerDelegate, CBPeripheralDelegate {
    @Published var host = UserDefaults.standard.string(forKey: "c4host") ?? ""
    @Published var token = ""
    @Published var vehicleStatus = "C4 尚未連線"
    @Published var values = "等待車況"
    @Published var bluetoothStatus = "藍牙尚未連線"
    @Published var currentLabel = "清屏"
    @Published var ready = false
    @Published var enabled = false
    @Published var customSlots = Array(repeating: CustomSlot(), count: 5)
    @Published var customStatus = "儲存後選擇顯示；車況提示優先。"
    private var activeSlot: Int?
    private var lastDisplayKey: String?
    private var pendingCustom = false
    private var central: CBCentralManager!
    private var peripheral: CBPeripheral?
    private var writeCharacteristic: CBCharacteristic?
    private var notifyCharacteristic: CBCharacteristic?
    private var sequence: UInt16 = 1
    private var timer: Timer?
    private var lastSample = Date.distantPast
    private var isPolling = false
    private var generation = UUID()
    private var slowingSince: Date?
    private var hardSince: Date?
    private var slowing = false
    private var hard = false
    private var lastLabel: String?
    private var frames: [Data] = []
    private var queuedLabel: String?
    private var sending = false
    private var drawActive = false
    private var autoC4 = true
    private var reconnectAttempt = false
    private var firstScreenConnection = true
    private let keychainService = "tw.carrotled.bridge"

    override init() {
        super.init()
        token = readKey() ?? ""
        if let data = UserDefaults.standard.data(forKey: "ledCustomSlots"),
           let saved = try? JSONDecoder().decode([CustomSlot].self, from: data), saved.count == 5 {
            customSlots = saved
        }
        central = CBCentralManager(delegate: self, queue: .main,
            options: [CBCentralManagerOptionRestoreIdentifierKey: "tw.carrotled.central"])
        if !host.isEmpty && !token.isEmpty { connectC4() }
        Timer.scheduledTimer(withTimeInterval: 0.33, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self, self.ready, !self.enabled, self.activeSlot != nil else { return }
                self.requestDisplay("__custom__")
            }
        }
    }

    private func keyQuery() -> [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: keychainService,
         kSecAttrAccount as String: "c4-bridge"]
    }
    private func readKey() -> String? {
        var query = keyQuery()
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }
    private func saveKey(_ value: String) -> Bool {
        guard let data = value.data(using: .utf8) else { return false }
        let query = keyQuery()
        let status = SecItemUpdate(query as CFDictionary,
                                   [kSecValueData as String: data] as CFDictionary)
        if status == errSecSuccess { return true }
        guard status == errSecItemNotFound else { return false }
        var add = query
        add[kSecValueData as String] = data
        add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        return SecItemAdd(add as CFDictionary, nil) == errSecSuccess
    }
    func enterBackground() {
        // A suspended app cannot guarantee a timely clear; attempt it before suspension.
        invalidate()
    }
    func returnToForeground() {
        // Previous data is never considered fresh after suspension.
        lastSample = .distantPast
        lastDisplayKey = nil
        if enabled && ready { lastLabel = nil; requestDisplay("") }
        if autoC4 && timer == nil && !host.isEmpty && !token.isEmpty { connectC4() }
        if central.state == .poweredOn && !ready && !reconnectAttempt { reconnectScreen() }
    }
    private func reconnectScreen() {
        guard central.state == .poweredOn, !ready, !reconnectAttempt else { return }
        if let saved = UserDefaults.standard.string(forKey: "ledID"), let uuid = UUID(uuidString: saved),
           let device = central.retrievePeripherals(withIdentifiers: [uuid]).first {
            reconnectAttempt = true; peripheral = device; device.delegate = self
            bluetoothStatus = "正在重新連接屏幕"
            central.connect(device)
        } else { scan() }
    }

    func scan() {
        guard central.state == .poweredOn else { bluetoothStatus = "請開啟藍牙並允許 App 使用藍牙"; return }
        bluetoothStatus = "掃描中；請先讓 LOY PLAY 與 Mac 斷線"
        central.scanForPeripherals(withServices: [CBUUID(string: "FFF0")])
    }
    nonisolated func centralManagerDidUpdateState(_ central: CBCentralManager) {
        Task { @MainActor in if central.state == .poweredOn { self.reconnectScreen() } }
    }
    nonisolated func centralManager(_ central: CBCentralManager, willRestoreState dict: [String: Any]) {
        guard let device = (dict[CBCentralManagerRestoredStatePeripheralsKey] as? [CBPeripheral])?.first else { return }
        Task { @MainActor in
            self.peripheral = device; device.delegate = self
            if device.state == .connected { device.discoverServices([CBUUID(string: "FFF0")]) }
            else { self.reconnectAttempt = false; self.reconnectScreen() }
        }
    }
    nonisolated func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral,
                                    advertisementData: [String: Any], rssi RSSI: NSNumber) {
        guard peripheral.name == "YS5255140425" else { return }
        Task { @MainActor in
            central.stopScan(); self.peripheral = peripheral; peripheral.delegate = self
            self.reconnectAttempt = true
            self.bluetoothStatus = "正在連接屏幕"; central.connect(peripheral)
        }
    }
    nonisolated func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        peripheral.delegate = self
        peripheral.discoverServices([CBUUID(string: "FFF0")])
        Task { @MainActor in
            self.reconnectAttempt = false
            UserDefaults.standard.set(peripheral.identifier.uuidString, forKey: "ledID")
        }
    }
    nonisolated func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral, error: Error?) {
        Task { @MainActor in
            self.reconnectAttempt = false
            self.bluetoothStatus = "屏幕連線失敗，稍後重試"
            try? await Task.sleep(nanoseconds: 5_000_000_000)
            self.scan()
        }
    }
    nonisolated func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        Task { @MainActor in
            self.ready = false; self.writeCharacteristic = nil; self.drawActive = false
            self.frames = []; self.sending = false; self.lastLabel = nil; self.lastDisplayKey = nil
            self.bluetoothStatus = "屏幕已斷線，正在重新連接；請確認是否留有畫面"
            self.reconnectAttempt = false
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            self.reconnectScreen()
        }
    }
    nonisolated func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        peripheral.services?.filter { $0.uuid == CBUUID(string: "FFF0") }.forEach {
            peripheral.discoverCharacteristics([CBUUID(string: "FFF1"), CBUUID(string: "FFF2")], for: $0)
        }
    }
    nonisolated func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        let write = service.characteristics?.first { $0.uuid == CBUUID(string: "FFF2") && $0.properties.contains(.writeWithoutResponse) }
        let notify = service.characteristics?.first { $0.uuid == CBUUID(string: "FFF1") && $0.properties.contains(.notify) }
        guard let write, let notify else { return }
        peripheral.setNotifyValue(true, for: notify)
        Task { @MainActor in
            self.writeCharacteristic = write; self.notifyCharacteristic = notify; self.ready = true
            self.bluetoothStatus = "藍牙已連線；畫面需目視確認"
            if self.firstScreenConnection {
                self.firstScreenConnection = false
                self.power(false)
            } else {
                self.lastLabel = nil
            }
        }
    }
    nonisolated func peripheralIsReady(toSendWriteWithoutResponse peripheral: CBPeripheral) {
        Task { @MainActor in self.pump() }
    }
    func power(_ on: Bool) {
        guard ready else { return }
        enabled = false
        lastDisplayKey = nil
        if drawActive { enqueue([0x30, 0x01, 0x65]); drawActive = false }
        enqueue([4, 2, 0, on ? 1 : 0]); lastLabel = nil
        bluetoothStatus = on ? "已送開屏指令，請目視確認" : "已送關屏指令，請目視確認"
    }

    @discardableResult func saveSlots() -> Bool {
        guard customSlots.allSatisfy({ $0.text.count <= 16 && ($0.text.isEmpty || validHex($0.color)) }) else {
            customStatus = "文字最多 16 字，顏色請填 6 位十六進位數字。"; return false
        }
        if let data = try? JSONEncoder().encode(customSlots) {
            UserDefaults.standard.set(data, forKey: "ledCustomSlots")
            customStatus = "五組文字已儲存。"
            return true
        } else { customStatus = "儲存失敗。"; return false }
    }
    private func validHex(_ text: String) -> Bool {
        let bytes = Array(text.utf8)
        return bytes.count == 6 && bytes.allSatisfy { (48...57).contains($0) || (65...70).contains($0) || (97...102).contains($0) }
    }
    func activateSlot(_ index: Int) {
        guard (0..<5).contains(index), !customSlots[index].text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              customSlots[index].text.count <= 16, validHex(customSlots[index].color) else {
            customStatus = "請填入文字及 6 位顏色代碼。"; return
        }
        guard saveSlots() else { return }
        activeSlot = index; lastDisplayKey = nil
        customStatus = "已選自訂 \(index + 1)，有效車況提示優先。"
        if enabled && Date().timeIntervalSince(lastSample) < 0.9 { return }
        if ready && !enabled { requestDisplay("__custom__") }
    }
    func clearSlot() {
        activeSlot = nil; lastDisplayKey = nil; customStatus = "已取消自訂待機文字。"
        if ready && !enabled { requestDisplay("") }
    }
    func connectC4() {
        disconnectC4()
        let address = host.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !address.isEmpty, !token.isEmpty,
              let url = URL(string: "http://\(address):18765/carstate"), url.host == address else {
            vehicleStatus = "請輸入 C4 IP 與橋接金鑰"; return
        }
        guard saveKey(token) else { vehicleStatus = "無法儲存橋接金鑰，請檢查鑰匙圈"; return }
        UserDefaults.standard.set(address, forKey: "c4host")
        autoC4 = true
        generation = UUID()
        let id = generation
        vehicleStatus = "正在連接 C4"
        timer = Timer.scheduledTimer(withTimeInterval: 0.2, repeats: true) { [weak self] _ in
            Task { @MainActor in await self?.poll(url, id: id) }
        }
    }
    func disconnectC4() {
        autoC4 = false
        generation = UUID(); timer?.invalidate(); timer = nil
        lastSample = .distantPast; slowingSince = nil; hardSince = nil; slowing = false; hard = false
        vehicleStatus = "C4 已斷線"; values = "等待車況"
        if enabled { requestDisplay("") }
    }
    private func poll(_ url: URL, id: UUID) async {
        guard generation == id, !isPolling else { return }
        isPolling = true; defer { isPolling = false }
        var request = URLRequest(url: url, timeoutInterval: 0.7)
        request.setValue("Bearer " + token, forHTTPHeaderField: "Authorization")
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard generation == id else { return }
            guard let response = response as? HTTPURLResponse else { throw URLError(.badServerResponse) }
            if response.statusCode == 401 {
                invalidate()
                vehicleStatus = "橋接金鑰錯誤或已變更，請重新輸入"
                return
            }
            guard response.statusCode == 200 else { throw URLError(.badServerResponse) }
            let state = try JSONDecoder().decode(CarState.self, from: data)
            guard state.valid, let speed = state.speed, let accel = state.accel,
                  let brake = state.brake, let left = state.left, let right = state.right,
                  let gear = state.gear, speed.isFinite, accel.isFinite else {
                invalidate(); return
            }
            let now = Date(); lastSample = now
            vehicleStatus = "已收到 C4 車況"
            values = String(format: "%.1f km/h  %.2f m/s²  檔位 %@\n煞車 %d  左燈 %d  右燈 %d", speed * 3.6, accel, gear, brake ? 1 : 0, left ? 1 : 0, right ? 1 : 0)
            let label = choose(speed: speed, accel: accel, brake: brake, left: left, right: right, gear: gear.lowercased(), now: now)
            if enabled && ready { requestDisplay(label.isEmpty && activeSlot != nil ? "__custom__" : label) }
        } catch {
            guard generation == id else { return }
            if Date().timeIntervalSince(lastSample) > 0.9 { invalidate() }
        }
    }
    private func invalidate() {
        vehicleStatus = "C4 資料中斷，嘗試清屏"
        slowing = false; hard = false; slowingSince = nil; hardSince = nil
        if enabled && ready { requestDisplay("") }
    }
    private func choose(speed: Double, accel: Double, brake: Bool, left: Bool, right: Bool, gear: String, now: Date) -> String {
        if slowing { if speed < 3.0/3.6 || accel >= -0.25 { slowing = false; slowingSince = nil } }
        else if speed >= 5.0/3.6 && accel <= -0.50 {
            if slowingSince == nil { slowingSince = now }; if now.timeIntervalSince(slowingSince!) >= 0.3 { slowing = true }
        } else { slowingSince = nil }
        if hard { if speed < 3.0/3.6 || accel >= -1.5 { hard = false; hardSince = nil } }
        else if speed >= 5.0/3.6 && accel <= -2.0 {
            if hardSince == nil { hardSince = now }; if now.timeIntervalSince(hardSince!) >= 0.3 { hard = true }
        } else { hardSince = nil }
        if left && right {
            if gear == "drive" && hard { return "前方塞車" }
            if gear == "park" { return "暫停一下謝謝" }
            if gear == "drive" { return "謝謝" }
            return ""
        }
        if left { return "左轉彎" }; if right { return "右轉彎" }
        if gear == "drive" && (brake || slowing) { return "減速中" }
        return ""
    }
    private func requestDisplay(_ label: String) {
        let slot = label == "__custom__" ? activeSlot.map { customSlots[$0] } : nil
        let tick = Int(Date().timeIntervalSince1970 * 3)
        var phase = 0
        if let slot = slot, slot.effect != "static" { phase = tick }
        let turn = label == "左轉彎" || label == "右轉彎"
        if turn { phase = tick }
        let key = "\(label)|\(slot?.text ?? "")|\(slot?.color ?? "")|\(slot?.effect ?? "")|\(slot?.bold ?? false)|\(phase)"
        if sending || !frames.isEmpty { queuedLabel = label; return }
        guard key != lastDisplayKey else { return }
        lastDisplayKey = key; lastLabel = label
        let text = slot?.text ?? label
        currentLabel = text.isEmpty ? "清屏" : text
        if !drawActive { enqueue([0x30, 0x01, 0x90]); drawActive = true }
        let clear: [UInt8] = [0x32,0x0d,0x01,0,0,0,0, 0,0,0,0,95,0,15,0]
        let scrolling = slot?.effect == "left" || slot?.effect == "right"
        let animatedPattern = turn || ["arrowsLeft", "arrowsRight", "wave", "heart", "warning"].contains(slot?.effect ?? "")
        // An animated full-screen bitmap avoids the blank frame caused by clear+redraw.
        // Device behavior must still be visually verified for trails.
        if !(scrolling || animatedPattern) { enqueue(clear) }
        if text.isEmpty || (slot?.effect == "blink" && tick % 2 == 1) { return }
        let offset = slot?.effect == "left" ? -(tick * 2 % 96) : slot?.effect == "right" ? (tick * 2 % 96) : 0
        let pattern = turn ? (label == "左轉彎" ? "turnLeft" : "turnRight") : (slot?.effect ?? "static")
        guard let pixels = bitmap(text, offset: offset, customBold: slot?.bold, pattern: pattern, phase: tick) else { return }
        var rgb: [UInt8] = label == "減速中" ? [255,48,32] : [255,180,0]
        if let slot = slot, let color = UInt32(slot.color, radix: 16) {
            rgb = [UInt8((color >> 16) & 255), UInt8((color >> 8) & 255), UInt8(color & 255)]
            if slot.effect == "breathe" {
                let levels: [Double] = [0.25,0.4,0.6,0.8,1.0,0.8,0.6,0.4]
                rgb = rgb.map { UInt8(Double($0) * levels[tick % 8]) }
            } else if slot.effect == "rainbow" {
                let color = UIColor(hue: CGFloat(tick % 12) / 12, saturation: 1, brightness: 1, alpha: 1)
                var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
                color.getRed(&r, green: &g, blue: &b, alpha: &a)
                rgb = [UInt8(r*255), UInt8(g*255), UInt8(b*255)]
            }
        }
        var content: [UInt8] = [0x00] + rgb + [0,0,0,0,95,0,15,0]
        content += pixels
        var command: [UInt8] = [0x32]
        if content.count < 128 { command += [UInt8(content.count)] }
        else { command += [0x81, UInt8(content.count)] }
        command += content
        enqueue(command)
    }
    private func bitmap(_ text: String, offset: Int = 0, customBold: Bool? = nil,
                        pattern: String = "static", phase: Int = 0) -> [UInt8]? {
        let size = CGSize(width: 96, height: 16)
        let format = UIGraphicsImageRendererFormat(); format.scale = 1; format.opaque = true
        let image = UIGraphicsImageRenderer(size: size, format: format).image { context in
            UIColor.black.setFill(); context.fill(CGRect(origin: .zero, size: size))
            // Thin dense turning glyphs to preserve their strokes at 16 px.
            let turnMessage = (text == "左轉彎" || text == "右轉彎")
            let useBold = customBold ?? !turnMessage
            let font = UIFont.systemFont(ofSize: 14, weight: useBold ? .bold : .regular)
            let attributes: [NSAttributedString.Key: Any] = [.font: font, .foregroundColor: UIColor.white]
            // Nonbreaking spaces keep every user-entered space measurable and visible.
            let rendered = text.replacingOccurrences(of: " ", with: "\u{00A0}") as NSString
            let hasEdgePattern = ["turnLeft", "turnRight", "arrowsLeft", "arrowsRight", "wave", "heart", "warning"].contains(pattern)
            let measured = rendered.size(withAttributes: attributes)
            let availableWidth: CGFloat = hasEdgePattern ? 68 : 94
            let scale = min(1, availableWidth / max(1, measured.width))
            context.cgContext.saveGState()
            let x = (96 - measured.width * scale) / 2 + CGFloat(offset)
            for wrap in [-96, 0, 96] {
                context.cgContext.saveGState()
                context.cgContext.translateBy(x: x + CGFloat(wrap), y: (16 - measured.height * scale) / 2)
                context.cgContext.scaleBy(x: scale, y: scale)
                rendered.draw(at: .zero, withAttributes: attributes)
                context.cgContext.restoreGState()
            }
            context.cgContext.restoreGState()
            let cg = context.cgContext
            cg.setStrokeColor(UIColor.white.cgColor)
            cg.setLineWidth(1)
            if ["turnLeft", "turnRight", "arrowsLeft", "arrowsRight"].contains(pattern) {
                let left = pattern == "turnLeft" || pattern == "arrowsLeft"
                // Two animated chevrons move within the side margin.
                let direction: CGFloat = left ? -1 : 1
                let shift = CGFloat(phase % 4) * direction
                let center: CGFloat = left ? 7 : 88
                for step in [-4, 3] {
                    let x = center + CGFloat(step) + shift
                    guard x >= 2 && x <= 93 else { continue }
                    cg.move(to: CGPoint(x: x - direction * 3, y: 4))
                    cg.addLine(to: CGPoint(x: x, y: 8))
                    cg.addLine(to: CGPoint(x: x - direction * 3, y: 12))
                }
                cg.strokePath()
            } else if pattern == "wave" {
                for base in [0, 82] {
                    cg.move(to: CGPoint(x: CGFloat(base), y: 8))
                    for dx in 1...13 {
                        let y = 8 + 3 * sin((Double(dx) + Double(phase * 2)) * .pi / 6)
                        cg.addLine(to: CGPoint(x: CGFloat(base + dx), y: CGFloat(y)))
                    }
                }
                cg.strokePath()
            } else if pattern == "warning" {
                for center in [7, 88] {
                    let x = CGFloat(center)
                    cg.move(to: CGPoint(x: x, y: 2)); cg.addLine(to: CGPoint(x: x - 6, y: 13))
                    cg.addLine(to: CGPoint(x: x + 6, y: 13)); cg.closePath()
                    if phase % 2 == 0 {
                        cg.move(to: CGPoint(x: x, y: 5)); cg.addLine(to: CGPoint(x: x, y: 9))
                        cg.move(to: CGPoint(x: x, y: 11)); cg.addLine(to: CGPoint(x: x, y: 12))
                    }
                }
                cg.strokePath()
            } else if pattern == "heart" {
                let expansion: CGFloat = phase % 4 < 2 ? 0 : 1
                for center in [7, 88] {
                    let x = CGFloat(center)
                    cg.move(to: CGPoint(x: x, y: 12 + expansion))
                    cg.addCurve(to: CGPoint(x: x, y: 5), control1: CGPoint(x: x - 9 - expansion, y: 6), control2: CGPoint(x: x - 4, y: 1))
                    cg.addCurve(to: CGPoint(x: x, y: 12 + expansion), control1: CGPoint(x: x + 4, y: 1), control2: CGPoint(x: x + 9 + expansion, y: 6))
                }
                cg.strokePath()
            }
        }
        guard let cg = image.cgImage else { return nil }
        var bytes = [UInt8](repeating: 0, count: 96 * 16 * 4)
        let ok = bytes.withUnsafeMutableBytes { raw -> Bool in
            guard let context = CGContext(data: raw.baseAddress, width: 96, height: 16, bitsPerComponent: 8,
                bytesPerRow: 96 * 4, space: CGColorSpaceCreateDeviceRGB(),
                bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return false }
            context.draw(cg, in: CGRect(x: 0, y: 0, width: 96, height: 16)); return true
        }
        guard ok else { return nil }
        var packed = [UInt8](repeating: 0, count: 12 * 16)
        for y in 0..<16 { for x in 0..<96 {
            let offset = (y * 96 + x) * 4
            if bytes[offset] > 100 { packed[y * 12 + x / 8] |= UInt8(0x80 >> (x % 8)) }
        }}
        return packed
    }
    private func enqueue(_ payload: [UInt8]) {
        guard let peripheral, let characteristic = writeCharacteristic else { return }
        let length = payload.count + 6
        var frame: [UInt8] = [0xaa,0x55,0xff,0xff, UInt8(length & 255), UInt8((length >> 8) & 255),
                              UInt8(sequence & 255), UInt8(sequence >> 8), 0xc1, 2]
        frame += payload
        let sum = frame.reduce(UInt32(0)) { $0 + UInt32($1) } & 0xffff
        frame += [UInt8(sum & 255), UInt8(sum >> 8)]
        sequence &+= 1
        let limit = max(1, min(180, peripheral.maximumWriteValueLength(for: .withoutResponse)))
        for start in stride(from: 0, to: frame.count, by: limit) {
            frames.append(Data(frame[start..<min(start + limit, frame.count)]))
        }
        _ = characteristic
        if !sending { sending = true; DispatchQueue.main.asyncAfter(deadline: .now() + 0.01) { self.pump() } }
    }
    private func pump() {
        guard ready, let peripheral, let characteristic = writeCharacteristic else { sending = false; return }
        guard peripheral.canSendWriteWithoutResponse else { return }
        guard !frames.isEmpty else {
            sending = false
            if let label = queuedLabel { queuedLabel = nil; requestDisplay(label) }
            return
        }
        let next = frames.removeFirst()
        peripheral.writeValue(next, for: characteristic, type: .withoutResponse)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.02) { self.pump() }
    }
}
