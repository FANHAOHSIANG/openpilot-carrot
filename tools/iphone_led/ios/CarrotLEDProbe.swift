import SwiftUI
import UIKit
import CoreBluetooth
import Security
import CoreText

@main
struct CarrotLEDProbeApp: App {
    @StateObject private var model = CarrotLED()
    @Environment(\.scenePhase) private var scenePhase
    var body: some Scene {
        WindowGroup {
            LEDInterface(model: model).onChange(of: scenePhase) { phase in
                if model.isScreenshotPreview { return }
                if phase == .active { model.returnToForeground() }
                if phase == .background { model.enterBackground() }
            }
        }
    }
}

struct LEDFontChoice: Identifiable {
    let id: String
    let title: String

    @MainActor
    static func available() -> [LEDFontChoice] {
        var choices = [
            LEDFontChoice(id: "standard", title: "系統標準"),
            LEDFontChoice(id: "rounded", title: "系統圓體"),
            LEDFontChoice(id: "monospaced", title: "系統等寬"),
            LEDFontChoice(id: "serif", title: "系統襯線")
        ]
        let names = Set(UIFont.familyNames.flatMap { UIFont.fontNames(forFamilyName: $0) }).sorted()
        let sample = Array("繁體中文轉彎倒車減速謝".utf16)
        for name in names {
            guard let font = UIFont(name: name, size: 32) else { continue }
            let ctFont = CTFontCreateWithName(name as CFString, 32, nil)
            var glyphs = [CGGlyph](repeating: 0, count: sample.count)
            guard CTFontGetGlyphsForCharacters(ctFont, sample, &glyphs, sample.count) else { continue }
            choices.append(LEDFontChoice(id: "font:" + name, title: "\(font.familyName) · \(name)"))
        }
        return choices
    }
}

struct FontMenu: View {
    let title: String
    @Binding var selection: String
    let choices: [LEDFontChoice]
    @State private var pickerSession: FontPickerSession?

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(.subheadline)
            Button {
                // Snapshot the choices and selection once per presentation.
                // Live vehicle updates must not restart an open font list.
                pickerSession = FontPickerSession(title: title, selection: selection, choices: choices)
            } label: {
                HStack {
                    Image(systemName: "textformat")
                    Text("選擇字型：\(choices.first(where: { $0.id == selection })?.title ?? selection)")
                        .lineLimit(2)
                        .frame(height: 44, alignment: .leading)
                    Spacer(minLength: 8)
                    Image(systemName: "chevron.right")
                }
                .padding(10)
                .background(Color.secondary.opacity(0.12), in: RoundedRectangle(cornerRadius: 8))
            }
            .sheet(item: $pickerSession) { session in
                FontPickerSheet(session: session) { chosen in
                    selection = chosen
                    pickerSession = nil
                }
                .id(session.id)
            }
            Text("系統樣式可能使用相同中文字型；其他選項已檢查部分繁體字，請以屏幕顯示為準。")
                .font(.caption).foregroundStyle(.secondary)
        }
    }
}

struct FontPickerSession: Identifiable {
    let id = UUID()
    let title: String
    let selection: String
    let choices: [LEDFontChoice]
}

struct FontPickerSheet: View {
    let session: FontPickerSession
    let onApply: (String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var draftSelection: String
    @State private var search = ""
    @State private var positionedInitially = false

    init(session: FontPickerSession, onApply: @escaping (String) -> Void) {
        self.session = session
        self.onApply = onApply
        _draftSelection = State(initialValue: session.selection)
    }

    private var visibleChoices: [LEDFontChoice] {
        let query = search.trimmingCharacters(in: .whitespacesAndNewlines)
        return query.isEmpty ? session.choices : session.choices.filter {
            $0.title.localizedCaseInsensitiveContains(query)
        }
    }

    var body: some View {
        NavigationStack {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 0) {
                        if visibleChoices.isEmpty {
                            Text("找不到符合的字型").foregroundStyle(.secondary).padding()
                        }
                        ForEach(visibleChoices) { choice in
                            Button { draftSelection = choice.id } label: {
                                HStack(spacing: 12) {
                                    Text(choice.title)
                                        .foregroundStyle(.primary)
                                        .multilineTextAlignment(.leading)
                                        .lineLimit(2)
                                    Spacer(minLength: 4)
                                    Image(systemName: "checkmark")
                                        .foregroundStyle(Color.accentColor)
                                        .frame(width: 22)
                                        .opacity(draftSelection == choice.id ? 1 : 0)
                                }
                                .frame(minHeight: 44)
                                .padding(.horizontal)
                                .padding(.vertical, 6)
                                .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                            .accessibilityValue(draftSelection == choice.id ? "已選取" : "未選取")
                            .id(choice.id)
                            Divider()
                        }
                    }
                }
                .onAppear {
                    guard !positionedInitially else { return }
                    positionedInitially = true
                    // Scroll only when this picker opens, never on selection
                    // changes or incoming C4 messages.
                    DispatchQueue.main.async {
                        proxy.scrollTo(session.selection, anchor: .center)
                    }
                }
            }
            .navigationTitle(session.title)
            .navigationBarTitleDisplayMode(.inline)
            .searchable(text: $search, prompt: "搜尋字型名稱")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("取消") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("套用") { onApply(draftSelection) }
                        .disabled(!session.choices.contains(where: { $0.id == draftSelection }))
                }
            }
        }
    }
}

struct VehicleStyle: Codable {
    var text: String
    var color: String
    var effect: String
    var font: String = "standard"
    var bold: Bool = false
    private enum CodingKeys: String, CodingKey { case text, color, effect, font, bold }
    init(text: String, color: String, effect: String, font: String = "standard", bold: Bool = false) {
        self.text = text; self.color = color; self.effect = effect; self.font = font; self.bold = bold
    }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        text = try c.decode(String.self, forKey: .text)
        color = try c.decode(String.self, forKey: .color)
        effect = try c.decode(String.self, forKey: .effect)
        font = try c.decodeIfPresent(String.self, forKey: .font) ?? UserDefaults.standard.string(forKey: "ledVehicleFont") ?? "standard"
        bold = try c.decodeIfPresent(Bool.self, forKey: .bold) ?? !["左轉彎", "右轉彎"].contains(decoder.codingPath.last?.stringValue ?? text)
    }
}

// Store the same RGB value as earlier versions, but let users choose it with
// the native iOS color picker instead of editing a hexadecimal string.
struct LEDColorPicker: View {
    @Binding var colorHex: String

    private var selectedColor: Binding<Color> {
        Binding(get: {
            let value = UInt32(colorHex, radix: 16) ?? 0xFFB400
            return Color(.sRGB,
                         red: Double((value >> 16) & 255) / 255,
                         green: Double((value >> 8) & 255) / 255,
                         blue: Double(value & 255) / 255)
        }, set: { color in
            let resolved = UIColor(color).resolvedColor(with: UITraitCollection.current)
            var red: CGFloat = 0, green: CGFloat = 0, blue: CGFloat = 0, alpha: CGFloat = 0
            if !resolved.getRed(&red, green: &green, blue: &blue, alpha: &alpha) {
                var white: CGFloat = 0
                guard resolved.getWhite(&white, alpha: &alpha) else { return }
                red = white; green = white; blue = white
            }
            func channel(_ component: CGFloat) -> Int {
                Int((min(1, max(0, component)) * 255).rounded())
            }
            colorHex = String(format: "%02X%02X%02X", channel(red), channel(green), channel(blue))
        })
    }

    var body: some View {
        ColorPicker("文字顏色", selection: selectedColor, supportsOpacity: false)
    }
}

struct VehicleStyleEditor: View {
    let event: String
    @Binding var setting: VehicleStyle
    let choices: [LEDFontChoice]
    let preview: () -> Void

    var body: some View {
        DisclosureGroup {
            VStack(alignment: .leading, spacing: 8) {
                TextField("顯示文字，最多 16 字", text: $setting.text)
                    .textFieldStyle(.roundedBorder)
                LEDColorPicker(colorHex: $setting.color)
                FontMenu(title: "此項字型", selection: $setting.font, choices: choices)
                Toggle("此項加粗", isOn: $setting.bold)
                Button("顯示預覽（5 秒）", action: preview)
                HStack {
                    Text("動畫效果")
                    Spacer()
                    Picker("動畫效果", selection: $setting.effect) {
                        Text("靜態").tag("static"); Text("閃爍").tag("blink")
                        Text("向左跑馬燈").tag("left"); Text("向右跑馬燈").tag("right")
                        Text("呼吸").tag("breathe"); Text("自動換色").tag("rainbow")
                        Text("向左箭頭").tag("arrowsLeft"); Text("向右箭頭").tag("arrowsRight")
                        Text("波浪圖案").tag("wave"); Text("愛心圖案").tag("heart")
                        Text("警示圖案").tag("warning")
                    }.pickerStyle(.menu).labelsHidden()
                }
            }.padding(.vertical, 6)
        } label: {
            VStack(alignment: .leading) {
                Text(event)
                Text(setting.text).font(.caption).foregroundStyle(.secondary)
            }
        }
    }
}

struct CustomSlot: Codable {
    var text = ""
    var color = "FFB400"
    var effect = "static"
    var bold = false
    var font = "standard"

    private enum CodingKeys: String, CodingKey { case text, color, effect, bold, font }
    init() {}
    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        text = try values.decodeIfPresent(String.self, forKey: .text) ?? ""
        color = try values.decodeIfPresent(String.self, forKey: .color) ?? "FFB400"
        effect = try values.decodeIfPresent(String.self, forKey: .effect) ?? "static"
        bold = try values.decodeIfPresent(Bool.self, forKey: .bold) ?? false
        font = try values.decodeIfPresent(String.self, forKey: .font) ?? "standard"
        if !["standard", "rounded", "monospaced", "serif"].contains(font) && !font.hasPrefix("font:") { font = "standard" }
    }
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
    var isScreenshotPreview: Bool {
        #if DEBUG
        return ProcessInfo.processInfo.arguments.contains("--ui-screenshot")
        #else
        return false
        #endif
    }
    @Published var host = UserDefaults.standard.string(forKey: "c4host") ?? ""
    @Published var token = ""
    @Published var vehicleStatus = "C4 尚未連線"
    @Published var values = "等待車況"
    @Published var bluetoothStatus = "藍牙尚未連線"
    @Published var currentLabel = "清屏"
    @Published var screenPowerOn = false
    @Published var eyesColor = UserDefaults.standard.string(forKey: "ledEyesColor") ?? "00DCC8" {
        didSet { UserDefaults.standard.set(eyesColor, forKey: "ledEyesColor"); lastDisplayKey = nil }
    }
    @Published var nativeEyes = UserDefaults.standard.object(forKey: "ledNativeEyes") as? Bool ?? true {
        didSet { UserDefaults.standard.set(nativeEyes,forKey:"ledNativeEyes"); lastDisplayKey = nil }
    }
    @Published var eyePlaybackStatus = "iPixel 可使用屏幕原生動畫；其他模式依藍牙速度播放"
    private var eyesActive = false
    private var eyesVariant = 0
    var vehicleIsFresh: Bool { Date().timeIntervalSince(lastSample) < 0.9 }
    private var idleLabel: String { eyesActive ? "__eyes__" : activeSlot != nil ? "__custom__" : "" }
    func activateEyes(_ variant: Int) {
        guard ready else { return }
        if !screenPowerOn { power(true) }
        startup.cancel()
        endPreview(); eyesVariant = EyeAnimations.index(variant); eyesActive = true; activeSlot = nil; lastDisplayKey = nil
        customStatus = "眼睛動畫已選用，車況提示優先。"
        if !enabled { requestDisplay("__eyes__") }
    }
    @Published var ipixel = UserDefaults.standard.bool(forKey: "ledIPixel")
    @Published var screens: [UUID: String] = [:]
    private var discoveredScreens: [UUID: CBPeripheral] = [:]
    private var screenIDKey: String { ipixel ? "ledIPixelID" : "ledID" }
    private var ipixelPackets: [[UInt8]] = []
    private var ipixelWriting = false
    private var ipixelAwaitingAck = false
    private var ipixelAckSeen = false
    private var ipixelFinalAckRequired = false
    private var scanGeneration = UUID()
    private var txGeneration = UUID()
    @Published var ready = false
    @Published var enabled = false
    @Published var vehicleFont = UserDefaults.standard.string(forKey: "ledVehicleFont") ?? "standard" {
        didSet {
            UserDefaults.standard.set(vehicleFont, forKey: "ledVehicleFont")
            lastDisplayKey = nil
        }
    }
    @Published var customSlots = Array(repeating: CustomSlot(), count: 5)
    @Published var customStatus = "儲存後選擇顯示；車況提示優先。"
    let eventKeys = ["倒車", "左轉彎", "右轉彎", "減速中", "暫停一下謝謝", "謝謝", "前方塞車"]
    let fontChoices = LEDFontChoice.available()
    @Published var vehicleDrafts = [String: VehicleStyle]()
    @Published var vehicleSettingsStatus = "各項車況可設定文字、顏色及動畫。"
    @Published var settingsStatus = "設定值須符合實際屏幕尺寸。"
    @Published var widthDraft = "96"
    @Published var heightDraft = "16"
    @Published var fontHeightDraft = "16"
    @Published var fontWidthDraft = "100"
    private var vehicleStyles = [String: VehicleStyle]()
    private var panelWidth = 96
    private var panelHeight = 16
    private var fontHeight = 16
    private var fontWidthPercent = 100
    private var activeSlot: Int?
    private var previewStyle: VehicleStyle?
    private var previewUntil = Date.distantPast
    @Published var previewStatus = ""
    var automaticBinding: Binding<Bool> {
        Binding(get: { self.enabled }, set: { value in
            if value && !self.screenPowerOn { self.power(true) }; self.startup.cancel(); self.endPreview(); self.enabled = value; self.lastDisplayKey = nil
            if self.ready { self.requestDisplay(!value ? self.idleLabel : "") }
        })
    }
    func eventTitle(_ key: String) -> String {
        let names = ["R檔", "左方向燈", "右方向燈", "煞車", "雙黃燈", "感謝燈", "急煞提示"]
        return eventKeys.firstIndex(of: key).map { names[$0] } ?? key
    }
    func eventText(_ key: String) -> String { vehicleStyles[key]?.text ?? key }
    func previewVehicle(_ key: String, draft: Bool = false) {
        guard ready else { previewStatus = "請先連接屏幕"; return }
        if !screenPowerOn { power(true) }
        guard let style = (draft ? vehicleDrafts[key] : vehicleStyles[key]),
              !style.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              style.text.count <= 16, validHex(style.color) else { previewStatus = "請先填入有效文字與顏色"; return }
        startup.cancel()
        previewStyle = style; previewUntil = Date().addingTimeInterval(5)
        previewStatus = "手動預覽：\(eventTitle(key))（5 秒，暫停自動顯示）"
        lastDisplayKey = nil; requestDisplay("__preview__")
    }
    func endPreview() {
        if queuedLabel == "__preview__" { queuedLabel = nil }
        previewStyle = nil; previewUntil = .distantPast; previewStatus = ""; lastDisplayKey = nil
    }
    private var lastDisplayKey: String?
    private var pendingCustom = false
    private var central: CBCentralManager!
    private var peripheral: CBPeripheral?
    private var writeCharacteristic: CBCharacteristic?
    private var notifyCharacteristic: CBCharacteristic?
    private var sequence: UInt16 = 1
    private var timer: Timer?
    let drivingSession = DrivingSession()
    private var inBackground = false
    private var lastSample = Date.distantPast
    private var isPolling = false
    private var generation = UUID()
    private let vehicleRules = VehicleRules()
    private let startup = StartupPlayback()
    private var latestVehicleLabel = ""
    private var lastLabel: String?
    private var frames: [Data] = []
    private var queuedLabel: String?
    private var sending = false
    private var loyPumpScheduled = false
    private var loyPumpGeneration = UUID()
    private var nextLoyWrite: TimeInterval = 0
    private var drawActive = false
    private let loyCanvas = LoyCanvas()
    private var loyBatch = true
    private var autoC4 = true
    private var reconnectAttempt = false
    private var firstScreenConnection = true
    private let keychainService = "tw.carrotled.bridge"

    override init() {
        super.init()
        drivingSession.onEnded = { [weak self] in
            guard let self, self.inBackground else { return }
            self.invalidate()
        }
        if !UserDefaults.standard.bool(forKey: "ledUI21AutoStartConfigured") {
            drivingSession.setAutoStart(true)
            UserDefaults.standard.set(true, forKey: "ledUI21AutoStartConfigured")
        }
        token = readKey() ?? ""
        let oldTexts = UserDefaults.standard.dictionary(forKey: "ledVehicleTexts") as? [String: String] ?? [:]
        let savedStyles: [String: VehicleStyle]
        if let data = UserDefaults.standard.data(forKey: "ledVehicleStyles"),
           let decoded = try? JSONDecoder().decode([String: VehicleStyle].self, from: data) {
            savedStyles = decoded
        } else { savedStyles = [:] }
        for event in eventKeys {
            var style = savedStyles[event] ?? defaultVehicleStyle(for: event)
            if savedStyles[event] == nil, let old = oldTexts[event] { style.text = old }
            if !validHex(style.color) { style.color = defaultVehicleStyle(for: event).color }
            if !Self.allowedEffects.contains(style.effect) { style.effect = defaultVehicleStyle(for: event).effect }
            vehicleStyles[event] = style
        }
        vehicleDrafts = vehicleStyles
        let savedWidth = UserDefaults.standard.integer(forKey: "ledPanelWidth")
        let savedHeight = UserDefaults.standard.integer(forKey: "ledPanelHeight")
        let savedFontHeight = UserDefaults.standard.integer(forKey: "ledFontHeight")
        let savedFontWidth = UserDefaults.standard.integer(forKey: "ledFontWidthPercent")
        if (8...256).contains(savedWidth), (8...64).contains(savedHeight) { panelWidth = savedWidth; panelHeight = savedHeight }
        fontHeight = (1...panelHeight).contains(savedFontHeight) ? savedFontHeight : panelHeight
        fontWidthPercent = (50...200).contains(savedFontWidth) ? savedFontWidth : 100
        widthDraft = String(panelWidth); heightDraft = String(panelHeight)
        fontHeightDraft = String(fontHeight); fontWidthDraft = String(fontWidthPercent)
        if let data = UserDefaults.standard.data(forKey: "ledCustomSlots"),
           let saved = try? JSONDecoder().decode([CustomSlot].self, from: data), saved.count == 5 {
            customSlots = saved
        }
        for index in customSlots.indices where !validHex(customSlots[index].color) {
            customSlots[index].color = "FFB400"
        }
        if isScreenshotPreview {
            ready = true; screenPowerOn = true; enabled = true; ipixel = true
            currentLabel = "減速中"; vehicleStatus = "已收到 C4 車況"; lastSample = Date.distantFuture
            bluetoothStatus = "iPixel · 介面示範"; customSlots[0].text = "Baby in car"
            return
        }
        // Only request restoration if the *built app* declares the central
        // background mode. Some Xcode projects generate a different Info.plist.
        let modes = Bundle.main.object(forInfoDictionaryKey: "UIBackgroundModes") as? [String] ?? []
        if modes.contains("bluetooth-central") {
            central = CBCentralManager(delegate: self, queue: .main,
                options: [CBCentralManagerOptionRestoreIdentifierKey: "tw.carrotled.central"])
        } else {
            central = CBCentralManager(delegate: self, queue: .main)
            bluetoothStatus = "背景藍牙未啟用，前景仍可連線"
        }
        if !host.isEmpty && !token.isEmpty { connectC4() }
        Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self, self.ready, self.screenPowerOn,
                      !self.inBackground || self.drivingSession.active else { return }
                if self.startup.active { self.tickStartup(); return }
                guard !self.ipixel, self.previewStyle == nil, self.idleLabel == "__eyes__",
                      !self.enabled || (self.vehicleIsFresh && self.latestVehicleLabel.isEmpty) else { return }
                self.requestDisplay("__eyes__")
            }
        }
        Timer.scheduledTimer(withTimeInterval: 0.2, repeats: true) { [weak self] _ in
            Task { @MainActor in
                guard let self else { return }
                if self.startup.active {
                    self.updateDrivingSession()
                    if self.startup.active { return }
                }
                if self.previewStyle != nil {
                    if Date() < self.previewUntil && self.ready {
                        self.requestDisplay("__preview__"); self.updateDrivingSession(); return
                    }
                    self.endPreview(); self.requestDisplay("")
                }
                if self.enabled && Date().timeIntervalSince(self.lastSample) >= 0.9 { self.invalidate() }
                self.updateDrivingSession()
                guard !self.inBackground || self.drivingSession.active else { return }
                guard self.ready, self.screenPowerOn, !self.enabled, !self.idleLabel.isEmpty else { return }
                self.requestDisplay(self.idleLabel)
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
    func startDrivingSession() {
        drivingSession.start(sampledAt: lastSample, connected: ready, automatic: enabled, displayText: currentLabel)
    }
    private func updateDrivingSession() {
        drivingSession.update(sampledAt: lastSample, connected: ready, automatic: enabled, displayText: currentLabel)
    }
    func enterBackground() {
        let wasPreview = previewStyle != nil
        endPreview()
        if wasPreview && ready { requestDisplay("") }
        inBackground = true
        // Only the explicit experiment may continue polling in background.
        // Suspension still prevents the watchdog from guaranteeing a LED clear.
        if !drivingSession.active { startup.cancel(); invalidate() }
    }
    func returnToForeground() {
        inBackground = false
        // Previous data is never considered fresh after suspension.
        lastSample = .distantPast
        lastDisplayKey = nil
        if enabled && ready { lastLabel = nil; requestDisplay("") }
        if autoC4 && timer == nil && !host.isEmpty && !token.isEmpty { connectC4() }
        if central.state == .poweredOn && !ready && !reconnectAttempt { reconnectScreen() }
    }
    func selectScreenType(_ value: Bool) {
        guard value != ipixel else { return }
        central.stopScan()
        let old = peripheral; peripheral = nil
        if let old { central.cancelPeripheralConnection(old) }
        resetTransmission(); ready = false; screenPowerOn = false; reconnectAttempt = false
        writeCharacteristic = nil; notifyCharacteristic = nil
        screens = [:]; discoveredScreens = [:]
        ipixel = value; UserDefaults.standard.set(value, forKey: "ledIPixel")
        widthDraft = value ? "64" : "96"; heightDraft = "16"; fontHeightDraft = "16"
        applyDisplaySettings()
        bluetoothStatus = "已切換屏幕類型，請掃描並選擇屏幕；舊屏幕請目視確認已關閉"
    }
    private func resetTransmission() {
        startup.cancel()
        loyCanvas.reset(); loyBatch = true
        txGeneration = UUID(); frames = []; ipixelPackets = []
        loyPumpGeneration = UUID(); loyPumpScheduled = false; nextLoyWrite = 0
        sending = false; ipixelWriting = false; ipixelAwaitingAck = false; ipixelAckSeen = false
        queuedLabel = nil; lastDisplayKey = nil; lastLabel = nil; drawActive = false
    }
    private func reconnectScreen() {
        guard central.state == .poweredOn, !ready, !reconnectAttempt else { return }
        if let saved = UserDefaults.standard.string(forKey: screenIDKey), let uuid = UUID(uuidString: saved),
           let device = central.retrievePeripherals(withIdentifiers: [uuid]).first {
            discoveredScreens[uuid] = device; connectScreen(uuid)
        } else if !inBackground { scan() }
    }
    func connectScreen(_ id: UUID) {
        guard let device = discoveredScreens[id], central.state == .poweredOn else { return }
        central.stopScan()
        if let old = peripheral, old.identifier != id { central.cancelPeripheralConnection(old) }
        resetTransmission(); ready = false; writeCharacteristic = nil; notifyCharacteristic = nil
        peripheral = device; device.delegate = self; reconnectAttempt = true
        bluetoothStatus = "正在連接 \(device.name ?? "屏幕")"
        central.connect(device)
        let ticket = txGeneration
        DispatchQueue.main.asyncAfter(deadline: .now()+15) { [weak self] in
            guard let self, self.txGeneration == ticket, !self.ready else { return }
            self.bluetoothStatus = "屏幕握手逾時；請確認類型及原廠 App 已斷線"
            self.central.cancelPeripheralConnection(device)
        }
    }
    func scan() {
        guard central.state == .poweredOn else { bluetoothStatus = "請開啟藍牙並允許 App 使用藍牙"; return }
        guard !ready else { bluetoothStatus = "屏幕已連線"; return }
        guard !reconnectAttempt else { bluetoothStatus = "正在連線，請稍候"; return }
        central.stopScan(); screens = [:]; discoveredScreens = [:]
        scanGeneration = UUID(); let scanTicket = scanGeneration
        bluetoothStatus = "掃描中；請先讓 iPixel Color／LOY PLAY 與其他裝置斷線"
        central.scanForPeripherals(withServices: ipixel ? nil : [CBUUID(string: "FFF0")])
        DispatchQueue.main.asyncAfter(deadline: .now()+12) { [weak self] in
            guard let self, self.scanGeneration == scanTicket, !self.ready, !self.reconnectAttempt else { return }
            self.central.stopScan(); self.bluetoothStatus = "掃描結束，請從列表選擇屏幕；未找到可再掃描"
        }
    }
    nonisolated func centralManagerDidUpdateState(_ central: CBCentralManager) {
        Task { @MainActor in
            if central.state == .poweredOn { self.reconnectScreen() }
            else { self.ready = false; self.reconnectAttempt = false; self.writeCharacteristic = nil; self.notifyCharacteristic = nil; self.resetTransmission(); self.bluetoothStatus = "藍牙不可用，請開啟藍牙" }
        }
    }
    nonisolated func centralManager(_ central: CBCentralManager, willRestoreState dict: [String: Any]) {
        let devices = (dict[CBCentralManagerRestoredStatePeripheralsKey] as? [CBPeripheral]) ?? []
        Task { @MainActor in
            guard let saved = UserDefaults.standard.string(forKey: self.screenIDKey),
                  let device = devices.first(where: { $0.identifier.uuidString == saved }) else { return }
            self.peripheral = device; device.delegate = self
            if device.state == .connected { device.discoverServices(nil) }
            else { self.reconnectAttempt = false; self.reconnectScreen() }
        }
    }
    nonisolated func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral,
                                    advertisementData: [String: Any], rssi RSSI: NSNumber) {
        let name = advertisementData[CBAdvertisementDataLocalNameKey] as? String ?? peripheral.name ?? "未命名設備"
        Task { @MainActor in
            guard !self.ready && !self.reconnectAttempt else { return }
            self.discoveredScreens[peripheral.identifier] = peripheral
            self.screens[peripheral.identifier] = name
            if !self.ipixel && name == "YS5255140425" { self.connectScreen(peripheral.identifier) }
        }
    }
    nonisolated func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        Task { @MainActor in
            guard self.peripheral === peripheral else { return }
            peripheral.delegate = self; peripheral.discoverServices(nil)
        }
    }
    nonisolated func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral, error: Error?) {
        Task { @MainActor in
            guard self.peripheral === peripheral else { return }
            self.reconnectAttempt = false; self.bluetoothStatus = "屏幕連線失敗，稍後重新連線"
            let ticket = self.txGeneration
            try? await Task.sleep(nanoseconds: 5_000_000_000)
            guard self.txGeneration == ticket else { return }
            self.reconnectScreen()
        }
    }
    nonisolated func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        Task { @MainActor in
            guard self.peripheral === peripheral else { return }
            self.ready = false; self.screenPowerOn = false; self.writeCharacteristic = nil; self.notifyCharacteristic = nil; self.resetTransmission()
            self.bluetoothStatus = "屏幕已斷線，正在重新連接；請確認是否留有畫面"
            self.reconnectAttempt = false
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            self.reconnectScreen()
        }
    }
    nonisolated func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        Task { @MainActor in
            guard self.peripheral === peripheral, error == nil else { return }
            for service in peripheral.services ?? [] {
                if self.ipixel || service.uuid == CBUUID(string: "FFF0") {
                    peripheral.discoverCharacteristics(nil, for: service)
                }
            }
        }
    }
    nonisolated func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        Task { @MainActor in
            guard self.peripheral === peripheral, self.writeCharacteristic == nil, error == nil else { return }
            let writeID = CBUUID(string: self.ipixel ? "FA02" : "FFF2")
            let notifyID = CBUUID(string: self.ipixel ? "FA03" : "FFF1")
            let property: CBCharacteristicProperties = self.ipixel ? .write : .writeWithoutResponse
            guard let write = service.characteristics?.first(where: { $0.uuid == writeID && $0.properties.contains(property) }),
                  let notify = service.characteristics?.first(where: { $0.uuid == notifyID && $0.properties.contains(.notify) }) else { return }
            self.writeCharacteristic = write; self.notifyCharacteristic = notify
            self.bluetoothStatus = "已連上藍牙，正在確認屏幕通知…"
            peripheral.setNotifyValue(true, for: notify)
        }
    }
    nonisolated func peripheral(_ peripheral: CBPeripheral, didUpdateNotificationStateFor characteristic: CBCharacteristic, error: Error?) {
        Task { @MainActor in
            guard self.peripheral === peripheral, characteristic === self.notifyCharacteristic else { return }
            guard error == nil && characteristic.isNotifying && self.writeCharacteristic != nil else {
                self.ready = false; self.bluetoothStatus = "屏幕通知訂閱失敗，請重新連線"; return
            }
            self.ready = true; self.reconnectAttempt = false; self.firstScreenConnection = false
            UserDefaults.standard.set(peripheral.identifier.uuidString, forKey: self.screenIDKey)
            self.lastLabel = nil; self.lastDisplayKey = nil; self.power(true); self.enabled = true
            self.bluetoothStatus = "\(self.ipixel ? "iPixel" : "LOY") 已連線，車況連動已啟用；等待有效 C4 資料"
        }
    }
    nonisolated func peripheralIsReady(toSendWriteWithoutResponse peripheral: CBPeripheral) {
        Task { @MainActor in if self.peripheral === peripheral { self.pump() } }
    }
    nonisolated func peripheral(_ peripheral: CBPeripheral, didWriteValueFor characteristic: CBCharacteristic, error: Error?) {
        Task { @MainActor in
            guard self.peripheral === peripheral, self.ipixel, characteristic === self.writeCharacteristic else { return }
            if error != nil { self.bluetoothStatus = "iPixel 寫入失敗"; self.central.cancelPeripheralConnection(peripheral); return }
            self.ipixelWriting = false; self.pump()
        }
    }
    nonisolated func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        let data = characteristic.value.map { Array($0) } ?? []
        Task { @MainActor in
            guard self.peripheral === peripheral, characteristic === self.notifyCharacteristic, error == nil else { return }
            if !self.ipixel {
                if let status = LoyCanvas.ackStatus(data), status != 0 {
                    self.loyCanvas.reset(); self.lastDisplayKey = nil
                    if status == 3 { self.loyBatch = false }
                    self.bluetoothStatus = "LOY 拒絕繪圖指令，正在重新同步畫面"
                }
                return
            }
            guard self.ipixelAwaitingAck, IPixelProtocol.ack(data),
                  !self.ipixelFinalAckRequired || data[4] == 3 else { return }
            self.ipixelAckSeen = true; self.bluetoothStatus = "iPixel 已回覆接收（非畫面回讀）"; self.pump()
        }
    }
    func power(_ on: Bool) {
        endPreview()
        guard ready else { return }
        let wasOn = screenPowerOn
        screenPowerOn = on
        if !on { startup.cancel() }
        if on && !wasOn && StartupArtwork.supported(width: panelWidth, height: panelHeight) {
            queuedLabel = nil
            startup.begin(Int64(ProcessInfo.processInfo.systemUptime*1000))
        }
        if !on { enabled = false; activeSlot = nil; eyesActive = false; queuedLabel = nil; ipixelPackets = [] }
        lastDisplayKey = nil
        if ipixel { enqueue(IPixelProtocol.power(on)) }
        else {
            if drawActive { enqueue([0x30, 0x01, 0x65]); drawActive = false }
            enqueue([4, 2, 0, on ? 1 : 0])
        }
        lastLabel = nil
        bluetoothStatus = on ? "已送開屏指令，請目視確認" : "已送關屏指令，請目視確認"
        currentLabel = on ? "已送開屏指令" : "已送關屏指令"
        updateDrivingSession()
    }

    func clearScreen() {
        startup.cancel()
        endPreview()
        guard ready else { return }
        enabled = false; activeSlot = nil; eyesActive = false; queuedLabel = nil
        lastDisplayKey = nil; lastLabel = nil
        customStatus = "已清除自訂文字，車況連動已暫停。"
        currentLabel = "清屏中"
        requestDisplay("")
    }
    private static let allowedEffects: Set<String> = [
        "static", "blink", "left", "right", "breathe", "rainbow",
        "arrowsLeft", "arrowsRight", "wave", "heart", "warning"
    ]
    private func defaultVehicleStyle(for event: String) -> VehicleStyle {
        let text = event == "倒車" ? "倒車，請注意" : event
        let color = event == "減速中" ? "FF3020" : "FFB400"
        let effect = event == "左轉彎" ? "arrowsLeft" : event == "右轉彎" ? "arrowsRight" : "static"
        return VehicleStyle(text: text, color: color, effect: effect, font: vehicleFont, bold: !["左轉彎", "右轉彎"].contains(event))
    }
    func vehicleBinding(for event: String) -> Binding<VehicleStyle> {
        Binding(get: { self.vehicleDrafts[event] ?? self.defaultVehicleStyle(for: event) },
                set: { self.vehicleDrafts[event] = $0 })
    }
    func saveVehicleTexts() {
        var newStyles = [String: VehicleStyle]()
        for event in eventKeys {
            let style = vehicleDrafts[event] ?? defaultVehicleStyle(for: event)
            guard !style.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
                  style.text.count <= 16, validHex(style.color), Self.allowedEffects.contains(style.effect) else {
                vehicleSettingsStatus = "「\(event)」請填 1–16 字，並重新選擇顏色。"; return
            }
            newStyles[event] = style
        }
        guard let data = try? JSONEncoder().encode(newStyles) else {
            vehicleSettingsStatus = "車況設定儲存失敗。"; return
        }
        UserDefaults.standard.set(data, forKey: "ledVehicleStyles")
        UserDefaults.standard.set(newStyles.mapValues { $0.text }, forKey: "ledVehicleTexts")
        vehicleStyles = newStyles
        lastDisplayKey = nil
        vehicleSettingsStatus = "所有車況的文字、顏色和效果已儲存。"
    }
    func applyDisplaySettings() {
        guard let w = Int(widthDraft), (8...256).contains(w), let h = Int(heightDraft), (8...64).contains(h),
              let fh = Int(fontHeightDraft), (1...h).contains(fh), let fw = Int(fontWidthDraft), (50...200).contains(fw) else {
            settingsStatus = "寬 8–256、高 8–64，字高不可超過屏幕高，字寬 50–200%。"; return
        }
        if ipixel && h != 16 { settingsStatus = "iPixel 此版僅支援 16 排；請設定 64 × 16"; return }
        guard !sending && frames.isEmpty else { settingsStatus = "正在傳送，請稍後再按套用。"; return }
        if ready && drawActive && !ipixel { enqueue(clearCommand()) }
        startup.cancel()
        panelWidth = w; panelHeight = h; fontHeight = fh; fontWidthPercent = fw
        UserDefaults.standard.set(w, forKey: "ledPanelWidth"); UserDefaults.standard.set(h, forKey: "ledPanelHeight")
        UserDefaults.standard.set(fh, forKey: "ledFontHeight"); UserDefaults.standard.set(fw, forKey: "ledFontWidthPercent")
        lastDisplayKey = nil; settingsStatus = "已儲存屏幕與字體像素設定。"
    }
    private func word(_ value: Int) -> [UInt8] { [UInt8(value & 255), UInt8((value >> 8) & 255)] }
    private func drawCommand(_ data: [UInt8]) -> [UInt8] {
        if data.count < 128 { return [0x32, UInt8(data.count)] + data }
        if data.count < 256 { return [0x32, 0x81, UInt8(data.count)] + data }
        return [0x32, 0x82] + word(data.count) + data
    }
    private func clearCommand() -> [UInt8] {
        drawCommand([0x01,0,0,0,0] + word(0) + word(0) + word(panelWidth - 1) + word(panelHeight - 1))
    }
    private func drawPixels(_ pixels: [UInt8], color: [UInt8], compact: Bool = false) {
        if ipixel {
            if let data = IPixelProtocol.text(pixels,width:panelWidth,height:panelHeight,rgb:color) { enqueue(data) }
            return
        }
        for command in LoyBitmap.pixels(pixels, width: panelWidth, height: panelHeight, color: color, compact: compact) {
            enqueue(command)
        }
    }
    func testAllPixels() {
        guard ready else { return }
        if !screenPowerOn { power(true) }
        startup.cancel()
        endPreview()
        enabled = false; activeSlot = nil; eyesActive = false; queuedLabel = nil; lastDisplayKey = nil
        if !ipixel && !drawActive { enqueue([0x30, 0x01, 0x90]); drawActive = true }
        let rowBytes = (panelWidth + 7) / 8
        var pixels = [UInt8](repeating: 255, count: rowBytes * panelHeight)
        if panelWidth % 8 != 0 {
            let mask = UInt8((0xff << (8 - panelWidth % 8)) & 0xff)
            for y in 0..<panelHeight { pixels[y * rowBytes + rowBytes - 1] = mask }
        }
        drawPixels(pixels, color: [255,255,255])
        currentLabel = "\(panelWidth) × \(panelHeight) 全亮測試"
        customStatus = "請目視檢查燈珠；按清除屏幕結束。"
    }
    @discardableResult func saveSlots() -> Bool {
        guard customSlots.allSatisfy({ $0.text.count <= 16 && ($0.text.isEmpty || validHex($0.color)) }) else {
            customStatus = "文字最多 16 字；若顏色異常，請重新選擇。"; return false
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
        endPreview()
        guard (0..<5).contains(index), !customSlots[index].text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              customSlots[index].text.count <= 16, validHex(customSlots[index].color) else {
            customStatus = "請填入文字並選擇顏色。"; return
        }
        guard ready, saveSlots() else { return }
        if !screenPowerOn { power(true) }
        startup.cancel()
        eyesActive = false
        activeSlot = index; lastDisplayKey = nil
        customStatus = "已選自訂 \(index + 1)，有效車況提示優先。"
        if enabled && Date().timeIntervalSince(lastSample) < 0.9 { return }
        if ready && !enabled { requestDisplay("__custom__") }
    }
    func clearSlot() {
        startup.cancel()
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
        lastSample = .distantPast; vehicleRules.reset()
        vehicleStatus = "C4 已斷線"; values = "等待車況"
        if enabled { requestDisplay("") }
    }
    private func poll(_ url: URL, id: UUID) async {
        guard generation == id, !isPolling, !inBackground || drivingSession.active else { return }
        isPolling = true; defer { isPolling = false }
        let requestedAt = Date()
        var request = URLRequest(url: url, timeoutInterval: 0.7)
        request.setValue("Bearer " + token, forHTTPHeaderField: "Authorization")
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard generation == id, !inBackground || drivingSession.active else { return }
            guard Date().timeIntervalSince(requestedAt) < 0.9 else { invalidate(); return }
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
            let label = vehicleRules.choose(speed: speed, accel: accel, brake: brake, left: left, right: right, gear: gear.lowercased(), now: Int64(ProcessInfo.processInfo.systemUptime*1000))
            latestVehicleLabel = label
            if enabled && vehicleRules.emergencyActive && previewStyle != nil { endPreview() }
            if enabled && ready { requestDisplay(label.isEmpty ? idleLabel : label) }
        } catch {
            guard generation == id, !inBackground || drivingSession.active else { return }
            if Date().timeIntervalSince(lastSample) > 0.9 { invalidate() }
        }
    }
    private func invalidate() {
        lastSample = .distantPast
        updateDrivingSession()
        vehicleStatus = "C4 資料中斷，嘗試清屏"
        vehicleRules.reset(); latestVehicleLabel = ""
        if enabled && ready { requestDisplay("") }
    }
    private func requestDisplay(_ label: String) {
        if startup.active {
            // Vehicle alerts supersede the opener; idle updates wait until it ends.
            if label == "__preview__" || (enabled && vehicleIsFresh && eventKeys.contains(label)) {
                startup.cancel(); lastDisplayKey = nil
            } else { return }
        }
        if label == "__preview__" && previewStyle == nil { return }
        if label != "__preview__", previewStyle != nil, Date() < previewUntil { return }
        if label == "__eyes__" {
            let native = ipixel && nativeEyes && panelWidth == 64 && panelHeight == 16
                && (peripheral?.maximumWriteValueLength(for:.withResponse) ?? 0) >= 100
            let phase = Int(ProcessInfo.processInfo.systemUptime * (ipixel ? 5 : 20))
            let key = "eyes|\(eyesVariant)|\(eyesColor)|\(native ? 0 : phase)|\(native)"
            if sending || !frames.isEmpty { queuedLabel = label; return }
            guard key != lastDisplayKey else { return }; lastDisplayKey = key
            let name = EyeAnimations.names[EyeAnimations.index(eyesVariant)]
            if currentLabel != name { currentLabel = name }
            let color = UInt32(eyesColor,radix:16) ?? 0x00dcc8
            if native {
                guard let data = EyeAnimations.gif(eyesVariant,color:color), let packet = IPixelProtocol.gif(data) else {
                    eyePlaybackStatus = "眼睛素材讀取失敗，請重新安裝完整專案"; lastDisplayKey = nil; return
                }
                eyePlaybackStatus = "iPixel 原生動畫 · 20 fps 素材，屏幕循環播放"
                enqueue(packet)
            } else {
                let status = ipixel ? "相容播放 · 目標 5 fps，依藍牙吞吐量調整" : "LOY 局部更新 · 最高目標 20 fps，實際以屏幕為準"
                if eyePlaybackStatus != status { eyePlaybackStatus = status }
                guard let rgba = EyeAnimations.raster(eyesVariant,color:color,width:panelWidth,height:panelHeight,time:ProcessInfo.processInfo.systemUptime) else { return }
                drawEyeRGBA(rgba,color:color,fixed:eyesVariant>=6)
            }
            return
        }
        let slot = label == "__custom__" ? activeSlot.map { customSlots[$0] } : nil
        let vehicleStyle = label == "__preview__" ? previewStyle : vehicleStyles[label]
        let tick = Int(Date().timeIntervalSince1970 * 3)
        let effect = slot?.effect ?? vehicleStyle?.effect ?? "static"
        let phase = effect == "static" || (ipixel && ["left","right","blink","breathe","rainbow"].contains(effect)) ? 0 : tick
        let turn = label == "左轉彎" || label == "右轉彎"
        let fontChoice = slot?.font ?? vehicleStyle?.font ?? vehicleFont
        let displayText = slot?.text ?? vehicleStyle?.text ?? label
        let colorCode = slot?.color ?? vehicleStyle?.color ?? "FFB400"
        let key = "\(label)|\(displayText)|\(colorCode)|\(effect)|\(slot?.bold ?? vehicleStyle?.bold ?? false)|\(fontChoice)|\(phase)"
        if sending || !frames.isEmpty { queuedLabel = label; return }
        guard key != lastDisplayKey else { return }
        lastDisplayKey = key; lastLabel = label
        let text = displayText
        currentLabel = text.isEmpty ? "清屏" : text
        if ipixel {
            let nativeScroll = effect == "left" || effect == "right"
            let bold = slot?.bold ?? vehicleStyle?.bold ?? !turn
            let width = nativeScroll ? nativeStripWidth(text, bold: bold, choice: fontChoice) : panelWidth
            let pixels = text.isEmpty ? [UInt8](repeating: 0,count:((width+7)/8)*16)
                : bitmap(text,customBold:bold,fontChoice:fontChoice,pattern:effect,phase:tick,nativeWidth:width,nativeStrip:nativeScroll)
            let color = UInt32(colorCode,radix:16) ?? 0xffb400
            let rgb = [UInt8((color>>16)&255),UInt8((color>>8)&255),UInt8(color&255)]
            if let pixels, let data = IPixelProtocol.text(pixels,width:width,height:panelHeight,rgb:rgb,effect:effect) { enqueue(data) }
            return
        }
        let scrolling = effect == "left" || effect == "right"
        if text.isEmpty || (effect == "blink" && tick % 2 == 1) {
            sendLoyFrame(layers: [], colors: []); return
        }
        let offset = effect == "left" ? -(tick * 2) : effect == "right" ? (tick * 2) : 0
        guard let pixels = bitmap(text, offset: offset, customBold: slot?.bold ?? vehicleStyle?.bold ?? !turn, fontChoice: fontChoice, pattern: effect, phase: tick, scrolling: scrolling) else { return }
        var rgb: [UInt8] = [255,180,0]
        if let color = UInt32(colorCode, radix: 16) {
            rgb = [UInt8((color >> 16) & 255), UInt8((color >> 8) & 255), UInt8(color & 255)]
            if effect == "breathe" {
                let levels: [Double] = [0.25,0.4,0.6,0.8,1.0,0.8,0.6,0.4]
                rgb = rgb.map { UInt8(Double($0) * levels[tick % 8]) }
            } else if effect == "rainbow" {
                let color = UIColor(hue: CGFloat(tick % 12) / 12, saturation: 1, brightness: 1, alpha: 1)
                var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
                color.getRed(&r, green: &g, blue: &b, alpha: &a)
                rgb = [UInt8(r*255), UInt8(g*255), UInt8(b*255)]
            }
        }
        sendLoyFrame(layers: [pixels], colors: [rgb])
    }
    private func tickStartup() {
        let idle = !sending && frames.isEmpty && ipixelPackets.isEmpty && !ipixelWriting && !ipixelAwaitingAck
        let native = ipixel && nativeEyes && panelWidth == 64 && panelHeight == 16
            && (peripheral?.maximumWriteValueLength(for: .withResponse) ?? 0) >= 100
        let frame = startup.step(Int64(ProcessInfo.processInfo.systemUptime*1000), ready: ready,
            power: screenPowerOn, interrupt: enabled && vehicleIsFresh && !latestVehicleLabel.isEmpty,
            idle: idle, nativeMode: native, intervalMs: ipixel ? 200 : 50)
        if frame == StartupPlayback.native {
            if let data = StartupArtwork.gif(), let packet = IPixelProtocol.gif(data) {
                currentLabel = "胡蘿蔔車開走 · 開屏動畫"; enqueue(packet)
            } else { startup.cancel(); bluetoothStatus = "開屏素材缺失，請更新完整 App" }
        } else if frame >= 0 {
            if let layers = StartupArtwork.layers(width: panelWidth, frame: frame) {
                if currentLabel != "胡蘿蔔車開走 · 開屏動畫" { currentLabel = "胡蘿蔔車開走 · 開屏動畫" }
                if ipixel {
                    var merged = layers[1]
                    for layer in layers.dropFirst(2) { for i in merged.indices { merged[i] |= layer[i] } }
                    drawPixels(merged, color: StartupArtwork.colors[1])
                } else {
                    sendLoyFrame(layers: Array(layers.dropFirst()), colors: Array(StartupArtwork.colors.dropFirst()))
                }
            } else { startup.cancel(); bluetoothStatus = "開屏素材缺失，請更新完整 App" }
        }
        if !startup.active && ready && screenPowerOn {
            lastDisplayKey = nil
            let resume = enabled ? (vehicleIsFresh ? (latestVehicleLabel.isEmpty ? idleLabel : latestVehicleLabel) : "") : idleLabel
            requestDisplay(resume)
        }
    }

    private func selectedFont(_ fontChoice: String, bold: Bool) -> UIFont {
        let weight: UIFont.Weight = bold ? .bold : .regular
            let base = UIFont.systemFont(ofSize: 32, weight: weight)
            let font: UIFont
            switch fontChoice {
            case "rounded":
                font = base.fontDescriptor.withDesign(.rounded).map { UIFont(descriptor: $0, size: 32) } ?? base
            case "monospaced":
                font = UIFont.monospacedSystemFont(ofSize: 32, weight: weight)
            case "serif":
                font = base.fontDescriptor.withDesign(.serif).map { UIFont(descriptor: $0, size: 32) } ?? base
            case let name where name.hasPrefix("font:"):
                // Keep the exact selected face; descriptor-based bold can replace
                // the chosen Chinese font with an unexpected fallback face.
                font = UIFont(name: String(name.dropFirst(5)), size: 32) ?? base
            default:
                font = base
            }
        return font
    }
    private func nativeStripWidth(_ text: String, bold: Bool, choice: String) -> Int {
        let line = CTLineCreateWithAttributedString(NSAttributedString(string:text.replacingOccurrences(of:" ",with:"\u{00A0}"),attributes:[.font:selectedFont(choice,bold:bold)]))
        let bounds = CTLineGetBoundsWithOptions(line, [.useGlyphPathBounds])
        let advance = CGFloat(CTLineGetTypographicBounds(line,nil,nil,nil))
        guard bounds.height > 0, advance.isFinite else { return panelWidth }
        let width = Int(ceil(max(advance,bounds.maxX) * CGFloat(fontHeight) / bounds.height * CGFloat(fontWidthPercent)/100)) + 8
        return min(2040,max(8,((width+7)/8)*8))
    }
    private func bitmap(_ text: String, offset: Int = 0, customBold: Bool? = nil,
                        fontChoice: String = "standard", pattern: String = "static", phase: Int = 0, scrolling: Bool = false, nativeWidth: Int? = nil, nativeStrip: Bool = false) -> [UInt8]? {
        let panelWidth = nativeWidth ?? self.panelWidth
        let size = CGSize(width: CGFloat(panelWidth), height: CGFloat(panelHeight))
        let format = UIGraphicsImageRendererFormat(); format.scale = 1; format.opaque = true
        let image = UIGraphicsImageRenderer(size: size, format: format).image { context in
            UIColor.black.setFill(); context.fill(CGRect(origin: .zero, size: size))
            // Measure actual glyph ink, then scale it to the panel height.
            // The typographic width includes spaces; preserve those advances.
            let turnMessage = (pattern == "turnLeft" || pattern == "turnRight")
            let useBold = customBold ?? !turnMessage
            let font = selectedFont(fontChoice, bold: useBold)
            var attributes: [NSAttributedString.Key: Any] = [.font: font, .foregroundColor: UIColor.white]
            if useBold && fontChoice.hasPrefix("font:") {
                attributes[.strokeColor] = UIColor.white
                attributes[.strokeWidth] = -1.5
            }
            let rendered = text.replacingOccurrences(of: " ", with: "\u{00A0}")
            let line = CTLineCreateWithAttributedString(NSAttributedString(string: rendered, attributes: attributes))
            let bounds = CTLineGetImageBounds(line, context.cgContext)
            let width = CGFloat(CTLineGetTypographicBounds(line, nil, nil, nil))
            guard !bounds.isNull, bounds.height.isFinite, bounds.height > 0, width.isFinite else { return }
            let hasEdgePattern = ["turnLeft", "turnRight", "arrowsLeft", "arrowsRight", "wave", "heart", "warning"].contains(pattern)
            let availableWidth = CGFloat(panelWidth) * (hasEdgePattern ? 68.0 / 96.0 : 1.0)
            let inkHeight = max(CGFloat(1), bounds.height)
            let scaleY = CGFloat(fontHeight) / inkHeight
            var scaleX = scaleY * CGFloat(fontWidthPercent) / 100
            if !scrolling && !nativeStrip { scaleX = min(scaleX, availableWidth / max(CGFloat(1), width)) }
            let textWidth = width * scaleX
            let baseline = (CGFloat(panelHeight) - bounds.height * scaleY) / 2 + bounds.maxY * scaleY
            let period = max(CGFloat(panelWidth + 24), textWidth + 24)
            let distance = CGFloat(abs(offset)).truncatingRemainder(dividingBy: period)
            let start: CGFloat = nativeStrip ? 0 : scrolling ? (offset <= 0 ? CGFloat(panelWidth) - distance : -textWidth + distance) : (CGFloat(panelWidth) - textWidth) / 2
            let copies: [CGFloat] = scrolling ? [start - period, start, start + period] : [start]
            for x in copies {
                context.cgContext.saveGState()
                context.cgContext.translateBy(x: x, y: baseline)
                context.cgContext.scaleBy(x: scaleX, y: -scaleY)
                context.cgContext.textPosition = .zero
                CTLineDraw(line, context.cgContext)
                context.cgContext.restoreGState()
            }
            let cg = context.cgContext
            cg.scaleBy(x: CGFloat(panelWidth) / 96, y: CGFloat(panelHeight) / 16)
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
        var bytes = [UInt8](repeating: 0, count: panelWidth * panelHeight * 4)
        let ok = bytes.withUnsafeMutableBytes { raw -> Bool in
            guard let context = CGContext(data: raw.baseAddress, width: panelWidth, height: panelHeight, bitsPerComponent: 8,
                bytesPerRow: panelWidth * 4, space: CGColorSpaceCreateDeviceRGB(),
                bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return false }
            context.draw(cg, in: CGRect(x: 0, y: 0, width: CGFloat(panelWidth), height: CGFloat(panelHeight))); return true
        }
        guard ok else { return nil }
        let rowBytes = (panelWidth + 7) / 8
        var packed = [UInt8](repeating: 0, count: rowBytes * panelHeight)
        for y in 0..<panelHeight { for x in 0..<panelWidth {
            let offset = (y * panelWidth + x) * 4
            if bytes[offset] > 60 { packed[y * rowBytes + x / 8] |= UInt8(0x80 >> (x % 8)) }
        }}
        return packed
    }
    private func drawEyeRGBA(_ rgba: [UInt8],color: UInt32,fixed: Bool) {
        let base = [Int((color>>16)&255),Int((color>>8)&255),Int(color&255)]
        let palette = [[255,34,54],[104,7,25],[148,77,217],[198,140,250]]
        let peak = base.max() ?? 255, stride = (panelWidth+7)/8
        var layers = [[UInt8]](repeating:[UInt8](repeating:0,count:stride*panelHeight),count:4)
        for y in 0..<panelHeight { for x in 0..<panelWidth {
            let p = (y*panelWidth+x)*4
            let rgb = [Int(rgba[p]),Int(rgba[p+1]),Int(rgba[p+2])], value = rgb.max() ?? 0
            if value < (fixed ? 85 : 10) { continue }
            let white = (0..<3).contains { rgb[$0] > base[$0]+12 }
            var level = white ? 3 : value < peak/3 ? 0 : value < peak*2/3 ? 1 : 2
            if fixed {
                var best = Int.max
                for j in palette.indices {
                    let dr = rgb[0]-palette[j][0], dg = rgb[1]-palette[j][1], db = rgb[2]-palette[j][2]
                    let distance = dr*dr+dg*dg+db*db
                    if distance < best { best = distance; level = j }
                }
            }
            layers[level][y*stride+x/8] |= UInt8(128 >> (x%8))
        } }
        if ipixel {
            var merged = layers[0]
            for layer in layers.dropFirst() { for i in merged.indices { merged[i] |= layer[i] } }
            drawPixels(merged,color:fixed ? [255,34,54] : base.map { UInt8($0) })
        } else {
            var colors: [[UInt8]] = []
            for level in 0..<4 {
                if fixed { colors.append(palette[level].map { UInt8($0) }) }
                else if level == 3 { colors.append([255,255,255]) }
                else {
                    let factor = level + 1
                    colors.append(base.map { UInt8($0 * factor / 3) })
                }
            }
            sendLoyFrame(layers: layers, colors: colors)
        }
    }
    private func sendLoyFrame(layers: [[UInt8]], colors: [[UInt8]]) {
        guard ready, !ipixel, layers.count == colors.count else { return }
        let row = (panelWidth + 7) / 8
        guard layers.allSatisfy({ $0.count == row * panelHeight }), colors.allSatisfy({ $0.count == 3 }) else { return }
        if !drawActive { enqueue([0x30, 0x01, 0x90]); drawActive = true }
        var canvas = [UInt32](repeating: 0, count: panelWidth * panelHeight)
        for (index, layer) in layers.enumerated() {
            let rgb = colors[index]
            let color = UInt32(rgb[0]) << 16 | UInt32(rgb[1]) << 8 | UInt32(rgb[2])
            for y in 0..<panelHeight { for x in 0..<panelWidth where layer[y * row + x / 8] & UInt8(128 >> (x % 8)) != 0 {
                canvas[y * panelWidth + x] = color
            } }
        }
        for packet in loyCanvas.update(canvas, width: panelWidth, height: panelHeight, now: ProcessInfo.processInfo.systemUptime, batch: loyBatch) {
            enqueue(packet, canvasUpdate: true)
        }
    }
    private func enqueue(_ payload: [UInt8], canvasUpdate: Bool = false) {
        guard let peripheral, let characteristic = writeCharacteristic else { return }
        if ipixel {
            ipixelPackets.append(payload)
            if !sending { sending = true; pump() }
            return
        }
        if !canvasUpdate { loyCanvas.reset() }
        let length = payload.count + 6
        var frame: [UInt8] = [0xaa,0x55,0xff,0xff, UInt8(length & 255), UInt8((length >> 8) & 255),
                              UInt8(sequence & 255), UInt8(sequence >> 8), 0xc1, 2]
        frame += payload
        let sum = frame.reduce(UInt32(0)) { $0 + UInt32($1) } & 0xffff
        frame += [UInt8(sum & 255), UInt8(sum >> 8)]
        sequence &+= 1
        let limit = max(1, min(244, peripheral.maximumWriteValueLength(for: .withoutResponse)))
        for start in stride(from: 0, to: frame.count, by: limit) {
            frames.append(Data(frame[start..<min(start + limit, frame.count)]))
        }
        _ = characteristic
        if !sending { sending = true; scheduleLoyPump() }
    }
    private func pumpIPixel(_ device: CBPeripheral, _ characteristic: CBCharacteristic) {
        guard !ipixelWriting else { return }
        if frames.isEmpty && ipixelAwaitingAck {
            guard ipixelAckSeen else { return }
            ipixelAwaitingAck = false; ipixelAckSeen = false; txGeneration = UUID()
        }
        if frames.isEmpty && !ipixelPackets.isEmpty {
            let data = ipixelPackets.removeFirst()
            let limit = max(1,min(244,device.maximumWriteValueLength(for:.withResponse)))
            for start in stride(from:0,to:data.count,by:limit) { frames.append(Data(data[start..<min(start+limit,data.count)])) }
            ipixelAwaitingAck = true; ipixelAckSeen = false; ipixelFinalAckRequired = data.count > 5
            let ticket = UUID(); txGeneration = ticket
            DispatchQueue.main.asyncAfter(deadline:.now()+15) { [weak self] in
                guard let self,self.txGeneration == ticket,self.ipixelAwaitingAck else { return }
                self.bluetoothStatus = "iPixel 接收回覆逾時，重新連接；請確認畫面"
                self.central.cancelPeripheralConnection(device)
            }
        }
        guard !frames.isEmpty else {
            sending = false
            if let label = queuedLabel { queuedLabel = nil; requestDisplay(label) }
            return
        }
        ipixelWriting = true
        device.writeValue(frames.removeFirst(),for:characteristic,type:.withResponse)
    }
    private func scheduleLoyPump() {
        guard !loyPumpScheduled else { return }
        loyPumpScheduled = true
        let ticket = loyPumpGeneration
        let delay = max(0, nextLoyWrite - ProcessInfo.processInfo.systemUptime)
        DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [weak self] in
            guard let self, self.loyPumpGeneration == ticket else { return }
            self.loyPumpScheduled = false
            self.pump()
        }
    }
    private func pump() {
        guard ready, let peripheral, let characteristic = writeCharacteristic else { sending = false; return }
        if ipixel { pumpIPixel(peripheral, characteristic); return }
        guard peripheral.canSendWriteWithoutResponse else { return }
        guard !frames.isEmpty else {
            sending = false
            if let label = queuedLabel { queuedLabel = nil; requestDisplay(label) }
            return
        }
        let now = ProcessInfo.processInfo.systemUptime
        guard now >= nextLoyWrite else { scheduleLoyPump(); return }
        let next = frames.removeFirst()
        nextLoyWrite = now + 0.005
        peripheral.writeValue(next, for: characteristic, type: .withoutResponse)
        scheduleLoyPump()
    }
}
