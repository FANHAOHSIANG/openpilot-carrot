import SwiftUI
import UIKit

enum LEDTheme {
    static let background = Color(red: 0.043, green: 0.059, blue: 0.078)
    static let surface = Color(red: 0.082, green: 0.106, blue: 0.141)
    static let line = Color(red: 0.16, green: 0.20, blue: 0.25)
    static let accent = Color(red: 1, green: 0.70, blue: 0.28)
    static let green = Color(red: 0.33, green: 0.90, blue: 0.65)
    static func color(_ hex: String) -> Color {
        let value = UInt32(hex, radix: 16) ?? 0xffb400
        return Color(red: Double((value >> 16)&255)/255, green: Double((value >> 8)&255)/255, blue: Double(value&255)/255)
    }
    static func icon(_ key: String) -> String {
        switch key { case "倒車": return "arrow.uturn.backward"; case "左轉彎": return "arrow.left"
        case "右轉彎": return "arrow.right"; case "減速中": return "hand.raised.fill"
        case "暫停一下謝謝": return "pause.fill"; case "謝謝": return "heart.fill"
        case "前方塞車": return "exclamationmark.triangle.fill"; default: return "text.bubble.fill" }
    }
}

struct LEDPanel<Content: View>: View {
    let content: Content
    init(@ViewBuilder content: () -> Content) { self.content = content() }
    var body: some View {
        content.padding(18).frame(maxWidth: .infinity, alignment: .leading)
            .background(LEDTheme.surface, in: RoundedRectangle(cornerRadius: 22))
            .overlay(RoundedRectangle(cornerRadius: 22).stroke(LEDTheme.line, lineWidth: 1))
    }
}

struct LEDInterface: View {
    @ObservedObject var model: CarrotLED
    var body: some View {
        TabView {
            NavigationStack { LEDDashboard(model: model) }
                .tabItem { Label("快捷", systemImage: "square.grid.2x2.fill") }
            NavigationStack { LEDStylePage(model: model) }
                .tabItem { Label("文字與動畫", systemImage: "textformat") }
            NavigationStack { LEDSettingsPage(model: model) }
                .tabItem { Label("連線設定", systemImage: "slider.horizontal.3") }
        }
        .tint(LEDTheme.accent).preferredColorScheme(.dark)
        .toolbarBackground(LEDTheme.surface, for: .tabBar)
        .toolbarBackground(.visible, for: .tabBar)
        .toolbar { ToolbarItemGroup(placement: .keyboard) { Spacer(); Button("完成") {
            UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
        } } }
    }
}

struct LEDStatusPill: View {
    let title: String
    let online: Bool
    var body: some View {
        HStack(spacing: 6) { Circle().fill(online ? LEDTheme.green : Color.gray).frame(width: 6, height: 6)
            Text(title).font(.caption.weight(.medium))
        }.padding(.horizontal, 10).padding(.vertical, 8).background(LEDTheme.surface, in: Capsule())
    }
}

struct LEDDashboard: View {
    @ObservedObject var model: CarrotLED
    @State private var group = ProcessInfo.processInfo.arguments.contains("--eyes-preview") ? 2 : 0
    private let columns = [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)]
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                HStack { VStack(alignment: .leading, spacing: 4) {
                    Text(model.isScreenshotPreview ? "CARROT / LED · 介面示範" : "CARROT / LED").font(.caption.weight(.bold)).tracking(3).foregroundStyle(LEDTheme.accent)
                    Text("讓後車看見").font(.title2.bold())
                }; Spacer(); Image(systemName: "car.side.fill").font(.title2).foregroundStyle(LEDTheme.accent) }
                HStack(spacing: 8) {
                    LEDStatusPill(title: model.vehicleIsFresh ? "C4 已連線" : "C4 等待中", online: model.vehicleIsFresh)
                    LEDStatusPill(title: model.ready ? "屏幕已連線" : "屏幕未連線", online: model.ready)
                    LEDBackgroundPill(runtime: model.drivingRuntime)
                }
                LEDPanel {
                    VStack(alignment: .leading, spacing: 14) {
                        HStack { Label("目前送出", systemImage: "display").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                            Spacer(); Text(model.ipixel ? "iPixel · 64 × 16" : "LOY PLAY").font(.caption.monospaced()).foregroundStyle(LEDTheme.accent) }
                        Text(model.currentLabel).font(.system(size: 32, weight: .bold, design: .rounded))
                            .foregroundStyle(LEDTheme.accent).lineLimit(2).minimumScaleFactor(0.6)
                            .frame(maxWidth: .infinity, minHeight: 68, alignment: .leading)
                            .accessibilityLabel("最近送出內容：\(model.currentLabel)")
                        Text(model.previewStatus.isEmpty ? (model.enabled ? "車況優先 · 提示結束後恢復待機內容" : "自動車況已暫停") : model.previewStatus)
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }.overlay(RoundedRectangle(cornerRadius: 22).stroke(LEDTheme.accent.opacity(0.65), lineWidth: 1.5))
                HStack(spacing: 12) {
                    Button { model.power(!model.screenPowerOn) } label: {
                        VStack(spacing: 5) { Image(systemName: "power").font(.system(size: 25, weight: .semibold))
                            Text(!model.ready ? "未連線" : model.screenPowerOn ? "已開啟" : "已關閉").font(.caption.weight(.semibold)) }
                        .frame(width: 88, height: 74)
                        .foregroundStyle(model.screenPowerOn && model.ready ? LEDTheme.green : Color.gray)
                        .background(model.screenPowerOn && model.ready ? LEDTheme.green.opacity(0.12) : Color.black, in: RoundedRectangle(cornerRadius: 18))
                        .overlay(RoundedRectangle(cornerRadius: 18).stroke(model.screenPowerOn && model.ready ? LEDTheme.green : LEDTheme.line, lineWidth: 1))
                    }.buttonStyle(.plain).disabled(!model.ready).accessibilityLabel(model.screenPowerOn ? "關閉屏幕" : "開啟屏幕")
                    Button { model.clearScreen() } label: {
                        HStack(spacing: 12) { Image(systemName: "xmark.rectangle.fill").font(.title2)
                            VStack(alignment: .leading, spacing: 3) { Text("清除屏幕").font(.headline); Text("停止文字、動畫與連動").font(.caption) } }
                        .frame(maxWidth: .infinity, minHeight: 74).foregroundStyle(Color(red: 1, green: 0.54, blue: 0.48))
                        .background(Color(red: 0.24, green: 0.10, blue: 0.11), in: RoundedRectangle(cornerRadius: 18))
                    }.buttonStyle(.plain).disabled(!model.ready)
                }
                Toggle(isOn: model.automaticBinding) {
                    Label("自動車況", systemImage: "bolt.horizontal.fill").font(.headline)
                }.tint(LEDTheme.green).padding(16).background(LEDTheme.surface, in: RoundedRectangle(cornerRadius: 18))
                Picker("快捷分類", selection: $group) { Text("車況").tag(0); Text("自訂文字").tag(1); Text("眼睛動畫").tag(2) }.pickerStyle(.segmented)
                LazyVGrid(columns: columns, spacing: 12) {
                    if group == 0 {
                        ForEach(model.eventKeys, id: \.self) { key in
                            LEDQuickTile(title: model.eventTitle(key), detail: model.eventText(key), icon: LEDTheme.icon(key), color: LEDTheme.accent) { model.previewVehicle(key) }
                                .disabled(!model.ready)
                        }
                    } else if group == 1 {
                        ForEach(0..<5, id: \.self) { i in
                            LEDQuickTile(title: "自訂 \(i+1)", detail: model.customSlots[i].text.isEmpty ? "到文字頁新增內容" : model.customSlots[i].text, icon: "text.bubble.fill", color: LEDTheme.color(model.customSlots[i].color)) { model.activateSlot(i) }
                                .disabled(!model.ready || model.customSlots[i].text.isEmpty)
                        }
                    } else {
                        ForEach(EyeAnimations.displayOrder, id: \.self) { i in
                            Button { model.activateEyes(i) } label: {
                                VStack(alignment: .leading, spacing: 14) {
                                    LEDEyesPreview(variant: i, color: LEDTheme.color(model.eyesColor)).frame(height: 45)
                                    Text(EyeAnimations.names[i]).font(.headline).foregroundStyle(.white)
                                    Text(i >= 6 ? "佐助・點一下顯示" : "點一下顯示").font(.caption).foregroundStyle(.secondary)
                                }.padding(16).frame(maxWidth: .infinity, minHeight: 124, alignment: .leading)
                                    .background(LEDTheme.surface, in: RoundedRectangle(cornerRadius: 18))
                                    .overlay(RoundedRectangle(cornerRadius: 18).stroke(LEDTheme.line))
                            }.buttonStyle(.plain).disabled(!model.ready)
                        }
                    }
                }
                Text("車況預覽 5 秒後恢復。電源與內容依 App 指令顯示，非屏幕回讀。請停車設定。")
                    .font(.caption).foregroundStyle(.secondary)
            }.padding(20)
        }.background(LEDTheme.background).toolbar(.hidden, for: .navigationBar)
    }
}

struct LEDBackgroundPill: View {
    @ObservedObject var runtime: DrivingRuntime
    var body: some View { LEDStatusPill(title: runtime.active ? "背景任務已允許" : runtime.requesting ? "背景申請中" : "前景模式", online: runtime.active) }
}
struct LEDQuickTile: View {
    let title: String; let detail: String; let icon: String; let color: Color; let action: () -> Void
    @Environment(\.isEnabled) private var enabled
    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 13) {
                HStack { Image(systemName: icon).font(.system(size: 25, weight: .semibold)).foregroundStyle(color)
                    Spacer(); Image(systemName: "play.fill").font(.caption2).foregroundStyle(.secondary) }
                Text(title).font(.headline).foregroundStyle(.white)
                Text(detail).font(.subheadline).foregroundStyle(.secondary).lineLimit(2)
            }.frame(maxWidth: .infinity, minHeight: 116, alignment: .topLeading).padding(16)
                .background(LEDTheme.surface, in: RoundedRectangle(cornerRadius: 18))
                .overlay(RoundedRectangle(cornerRadius: 18).stroke(LEDTheme.line))
                .opacity(enabled ? 1 : 0.55)
        }.buttonStyle(.plain).accessibilityLabel("顯示\(title)，\(detail)")
    }
}

struct LEDEyesPreview: UIViewRepresentable {
    let variant: Int; let color: Color
    final class Coordinator { var key = "" }
    func makeCoordinator() -> Coordinator { Coordinator() }
    func makeUIView(context: Context) -> UIImageView {
        let view = UIImageView(); view.contentMode = .scaleAspectFit
        view.layer.magnificationFilter = .nearest; view.layer.minificationFilter = .nearest
        view.setContentHuggingPriority(.defaultLow,for:.horizontal)
        view.setContentCompressionResistancePriority(.defaultLow,for:.horizontal)
        view.accessibilityLabel = "眼睛動畫預覽"; return view
    }
    func updateUIView(_ view: UIImageView,context: Context) {
        var r: CGFloat = 0,g: CGFloat = 0,b: CGFloat = 0,a: CGFloat = 0
        UIColor(color).getRed(&r,green:&g,blue:&b,alpha:&a)
        let rgb = UInt32(r*255)<<16 | UInt32(g*255)<<8 | UInt32(b*255)
        let key = "\(variant):\(rgb)"
        guard context.coordinator.key != key else { return }
        context.coordinator.key = key; view.image = EyeAnimations.image(variant,color:rgb); view.startAnimating()
    }
    static func dismantleUIView(_ view: UIImageView,coordinator: Coordinator) { view.stopAnimating() }
}

struct LEDEffectPicker: View {
    @Binding var effect: String
    var body: some View {
        Picker("動畫效果", selection: $effect) {
            Text("靜態").tag("static"); Text("閃爍").tag("blink"); Text("向左跑馬燈").tag("left"); Text("向右跑馬燈").tag("right")
            Text("呼吸").tag("breathe"); Text("自動換色").tag("rainbow"); Text("向左箭頭").tag("arrowsLeft"); Text("向右箭頭").tag("arrowsRight")
            Text("波浪").tag("wave"); Text("愛心").tag("heart"); Text("警示").tag("warning")
        }
    }
}
struct LEDStylePage: View {
    @ObservedObject var model: CarrotLED
    @State private var group = ProcessInfo.processInfo.arguments.contains("--eyes-preview") ? 2 : 0
    var body: some View {
        Form {
            Section { Picker("分類", selection: $group) { Text("車況").tag(0); Text("自訂文字").tag(1); Text("眼睛").tag(2) }.pickerStyle(.segmented) }
            if group == 0 {
                Section("每項獨立設定") {
                    Text("急煞提示：D 檔 ≥20 km/h，減速度 ≥4.5 m/s² 持續 ≥0.3 秒（至少 3 筆），不需雙黃燈。觸發後交替提示至少 6 秒，離開 D 檔或資料失效取消。").font(.caption).foregroundStyle(.secondary)
                    ForEach(model.eventKeys, id: \.self) { event in
                        VehicleStyleEditor(event: model.eventTitle(event), setting: model.vehicleBinding(for: event), choices: model.fontChoices, preview: { model.previewVehicle(event, draft: true) })
                    }
                }
                Section { Button("儲存所有車況設定") { model.saveVehicleTexts() }; Text(model.vehicleSettingsStatus).font(.caption).foregroundStyle(.secondary) }
            } else if group == 1 {
                ForEach(0..<5, id: \.self) { i in
                    Section("自訂 \(i+1)") {
                        TextField("輸入文字（最多 16 字）", text: $model.customSlots[i].text)
                        LEDColorPicker(colorHex: $model.customSlots[i].color)
                        LEDEffectPicker(effect: $model.customSlots[i].effect)
                        FontMenu(title: "字型", selection: $model.customSlots[i].font, choices: model.fontChoices)
                        Toggle("加粗", isOn: $model.customSlots[i].bold)
                        HStack { Button("儲存") { model.saveSlots() }; Spacer(); Button("顯示") { model.activateSlot(i) }.disabled(!model.ready) }.buttonStyle(.bordered)
                    }
                }
                Section { Button("取消自訂待機文字") { model.clearSlot() }; Text(model.customStatus).font(.caption) }
            } else {
                Section("眼睛動畫") {
                    LEDEyesPreview(variant: 2, color: LEDTheme.color(model.eyesColor)).frame(height: 80)
                    LEDColorPicker(colorHex: $model.eyesColor)
                    Toggle("iPixel 原生平順動畫", isOn: $model.nativeEyes)
                    Text(model.eyePlaybackStatus).font(.caption).foregroundStyle(.secondary)
                    Text("共八款，新增佐助「寫輪眼 → 萬花筒」及「萬花筒 → 輪迴眼」。佐助兩款保留紅／紫配色，調色盤只調整原六款。原生模式上傳一次後由屏幕循環播放；若不相容可關閉。車況優先，清屏停止動畫。")
                        .font(.footnote).foregroundStyle(.secondary)
                }
            }
        }.navigationTitle("文字與動畫").scrollDismissesKeyboard(.interactively)
            .scrollContentBackground(.hidden).background(LEDTheme.background)
    }
}

struct LEDSettingsPage: View {
    @ObservedObject var model: CarrotLED
    var body: some View {
        Form {
            Section("C4 車況橋接") {
                TextField("C4 區網 IP", text: $model.host).textInputAutocapitalization(.never).autocorrectionDisabled()
                SecureField("橋接連線金鑰", text: $model.token).textInputAutocapitalization(.never).autocorrectionDisabled()
                HStack { Button("連接 C4") { model.connectC4() }; Spacer(); Button("斷開") { model.disconnectC4() } }.buttonStyle(.bordered)
                Text(model.vehicleStatus).font(.footnote); Text(model.values).font(.caption.monospaced()).foregroundStyle(.secondary)
            }
            Section("LED 屏幕") {
                Picker("屏幕類型", selection: Binding(get: { model.ipixel }, set: { model.selectScreenType($0) })) { Text("LOY PLAY").tag(false); Text("iPixel Color").tag(true) }
                Button("掃描屏幕") { model.scan() }
                ForEach(model.screens.keys.sorted(by: { $0.uuidString < $1.uuidString }), id: \.self) { id in
                    Button("連接：\(model.screens[id] ?? id.uuidString)") { model.connectScreen(id) }
                }
                Text(model.bluetoothStatus).font(.footnote)
                Button("燈珠全亮測試") { model.testAllPixels() }.disabled(!model.ready)
                Text("先讓原廠 App 與其他裝置斷開屏幕。iPixel 使用 64 × 16，LOY 使用 96 × 16。")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Section("自動啟動與背景") {
                Text("開 App 自動重連。要切換到其他 App，請先按下方「開始 60 分鐘連動」，等待 iOS 允許；動態島顯示與背景執行是兩件事。")
                    .font(.footnote).foregroundStyle(.secondary)
                DrivingSessionView(session: model.drivingSession, runtime: model.drivingRuntime,
                    start: { model.startDrivingSession() }, stop: { model.stopDrivingSession() })
            }
            Section("屏幕與文字像素") {
                pixelField("屏幕寬（燈珠）", value: $model.widthDraft)
                pixelField("屏幕高（燈珠）", value: $model.heightDraft)
                pixelField("文字高度（像素）", value: $model.fontHeightDraft)
                pixelField("文字寬度（%）", value: $model.fontWidthDraft)
                Button("套用像素設定") { model.applyDisplaySettings() }
                Text(model.settingsStatus).font(.caption).foregroundStyle(.secondary)
            }
            Section { Text("Carrot LED 0.23 · 字型、配色、點陣動畫\n電源與目前內容是 App 指令狀態，實體畫面請目視確認。")
                .font(.caption).foregroundStyle(.secondary) }
        }.navigationTitle("連線設定").scrollDismissesKeyboard(.interactively)
            .scrollContentBackground(.hidden).background(LEDTheme.background)
    }
    private func pixelField(_ label: String, value: Binding<String>) -> some View {
        HStack { Text(label); Spacer(); TextField(label, text: value).keyboardType(.numberPad).multilineTextAlignment(.trailing).frame(width: 80) }
    }
}
