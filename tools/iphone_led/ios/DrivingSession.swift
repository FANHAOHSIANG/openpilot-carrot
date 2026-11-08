import ActivityKit
import SwiftUI
import UIKit

// A Live Activity improves Bluetooth privileges on iOS 26+, not general CPU or
// LAN execution. Start automatically only while foreground and connections are fresh.
@MainActor
final class DrivingSession: ObservableObject {
    @Published private(set) var active = false
    @Published private(set) var message = "尚未開始行車即時動態"
    @Published private(set) var autoStart = UserDefaults.standard.object(forKey: "ledAutoBackground") as? Bool ?? true
    @Published var expandOnChange = UserDefaults.standard.object(forKey: "ledExpandOnChange") as? Bool ?? true {
        didSet {
            UserDefaults.standard.set(expandOnChange, forKey: "ledExpandOnChange")
            alertPolicy.reset(text: lastState?.displayText ?? "")
        }
    }
    private var alertPolicy = IslandAlertPolicy()
    private var nextAutoAttempt = Date.distantPast
    private var cleanupComplete = false
    private var activity: Activity<LEDActivityAttributes>?
    private var observer: Task<Void, Never>?
    @Published private(set) var islandUpdateStatus = "尚未提交動態島更新"
    private var updateTask: Task<Void, Never>?
    private var updateGeneration = UUID()
    private var pendingUpdate: (LEDActivityAttributes.ContentState, Date, AlertConfiguration?)?
    private var lastUpdate = Date.distantPast
    private var lastState: LEDActivityAttributes.ContentState?
    var onEnded: (() -> Void)?

    init() {
        // Never revive an old session or its stale vehicle status after relaunch.
        let orphans = Activity<LEDActivityAttributes>.activities
        Task {
            for item in orphans { await item.end(nil, dismissalPolicy: .immediate) }
            self.cleanupComplete = true
        }
    }

    func setAutoStart(_ value: Bool) {
        autoStart = value
        UserDefaults.standard.set(value, forKey: "ledAutoBackground")
        nextAutoAttempt = .distantPast
        if !value { stop() }
        else { message = "等待連線後自動顯示動態島；背景連動需另外按開始" }
    }

    private func tryAutoStart(sampledAt: Date, connected: Bool, automatic: Bool, displayText: String) {
        guard autoStart, !active, cleanupComplete,
              UIApplication.shared.applicationState == .active,
              connected, automatic, Date().timeIntervalSince(sampledAt) >= 0,
              Date().timeIntervalSince(sampledAt) < 0.9,
              Date() >= nextAutoAttempt else { return }
        // Do not hammer ActivityKit when permission or OS support is unavailable.
        nextAutoAttempt = Date().addingTimeInterval(30)
        start(sampledAt: sampledAt, connected: connected, automatic: automatic, displayText: displayText)
    }

    func start(sampledAt: Date, connected: Bool, automatic: Bool, displayText: String) {
        guard !active, cleanupComplete else { return }
        guard #available(iOS 26.0, *) else {
            message = "背景藍牙即時動態測試需要 iOS 26 或以上"; return
        }
        guard UIApplication.shared.applicationState == .active else { return }
        guard ActivityAuthorizationInfo().areActivitiesEnabled else {
            message = "即時動態未獲允許，請在 iPhone 設定中開啟此 App 的即時動態"; return
        }
        guard connected, automatic, Date().timeIntervalSince(sampledAt) < 0.9 else {
            message = "請先連接屏幕、收到有效 C4 車況，並開啟自動顯示車況"; return
        }
        let state = LEDActivityAttributes.ContentState(sampledAt: sampledAt, fresh: true,
                                                       screenConnected: connected, automatic: automatic, displayText: displayText)
        do {
            let item = try Activity.request(attributes: LEDActivityAttributes(title: "Carrot 行車連動"),
                content: ActivityContent(state: state, staleDate: Date().addingTimeInterval(15)), pushType: nil)
            cancelUpdates()
            alertPolicy.reset(text: displayText)
            activity = item; active = true; lastState = state; lastUpdate = .distantPast
            message = "動態島已顯示；請確認背景任務已允許再切換 App"
            observer = Task { [weak self] in
                for await state in item.activityStateUpdates {
                    guard !Task.isCancelled else { return }
                    if state == .ended || state == .dismissed {
                        guard let self, self.activity?.id == item.id else { return }
                        self.cancelUpdates()
                        self.activity = nil; self.active = false
                        if state == .dismissed {
                            self.autoStart = false
                            UserDefaults.standard.set(false, forKey: "ledAutoBackground")
                        }
                        self.nextAutoAttempt = Date().addingTimeInterval(30)
                        self.message = "動態島已結束；背景任務狀態請看行車連動區"
                        self.onEnded?()
                        return
                    }
                }
            }
        } catch { message = "無法開始即時動態：\(error.localizedDescription)" }
    }

    func update(sampledAt: Date, connected: Bool, automatic: Bool, displayText: String) {
        tryAutoStart(sampledAt: sampledAt, connected: connected, automatic: automatic, displayText: displayText)
        guard let item = activity, active else { return }
        let now = Date()
        let fresh = now.timeIntervalSince(sampledAt) < 0.9
        let state = LEDActivityAttributes.ContentState(sampledAt: sampledAt, fresh: fresh,
                                                       screenConnected: connected, automatic: automatic, displayText: displayText)
        let isControl = displayText.isEmpty || ["清屏", "清屏中", "已送開屏指令", "已送關屏指令"].contains(displayText) || displayText.hasSuffix("全亮測試")
        let eligible = expandOnChange && connected && fresh && !isControl
            && UIApplication.shared.applicationState == .background
        let shouldExpand = alertPolicy.shouldAlert(text: displayText, eligible: eligible,
                                                  uptime: ProcessInfo.processInfo.systemUptime)
        let changed = lastState?.fresh != fresh || lastState?.screenConnected != connected || lastState?.automatic != automatic || lastState?.displayText != displayText
        // This deadline describes the UI snapshot, NOT vehicle-data validity.
        // C4 freshness remains 0.9 s and fresh=false is sent immediately.
        // Changed text/status bypasses the 5 s unchanged-content heartbeat.
        guard changed || shouldExpand || now.timeIntervalSince(lastUpdate) >= 5 else { return }
        lastState = state; lastUpdate = now
        // AlertConfiguration asks iOS to expand briefly; the system owns presentation timing.
        // The bundled silent sound avoids beeping on every vehicle-word change.
        let alert: AlertConfiguration? = shouldExpand && Bundle.main.url(forResource: "IslandSilent", withExtension: "wav") != nil
            ? AlertConfiguration(title: "Carrot LED", body: "\(displayText)", sound: .named("IslandSilent.wav")) : nil
        pendingUpdate = (state, now.addingTimeInterval(15), alert)
        guard updateTask == nil else { return }
        let generation = updateGeneration
        updateTask = Task { [weak self] in
            guard let self else { return }
            while !Task.isCancelled, self.updateGeneration == generation,
                  self.active, self.activity?.id == item.id, let pending = self.pendingUpdate {
                self.pendingUpdate = nil
                // Do not revive a queued snapshot or pop up an old alert after suspension.
                guard pending.1 > Date() else { continue }
                let stillFresh = Date().timeIntervalSince(pending.0.sampledAt) < 0.9
                var state = pending.0
                state.fresh = state.fresh && stillFresh
                await item.update(ActivityContent(state: state, staleDate: pending.1),
                                  alertConfiguration: state.fresh ? pending.2 : nil)
                guard self.updateGeneration == generation else { return }
                self.islandUpdateStatus = "最近完成提交：" + Date().formatted(date: .omitted, time: .standard)
            }
            guard self.updateGeneration == generation else { return }
            self.updateTask = nil
        }
    }

    private func cancelUpdates() {
        updateGeneration = UUID()
        updateTask?.cancel(); updateTask = nil; pendingUpdate = nil
    }

    func stop() {
        cancelUpdates()
        autoStart = false
        UserDefaults.standard.set(false, forKey: "ledAutoBackground")
        observer?.cancel(); observer = nil
        let item = activity
        activity = nil; active = false; message = "行車即時動態已停止"
        onEnded?()
        Task { await item?.end(nil, dismissalPolicy: .immediate) }
    }
}

struct DrivingSessionView: View {
    @ObservedObject var session: DrivingSession
    @ObservedObject var runtime: DrivingRuntime
    let start: () -> Void
    let stop: () -> Void
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("背景行車連動").font(.headline)
            Toggle("自動顯示行車動態島", isOn: Binding(get: { session.autoStart }, set: { session.setAutoStart($0) }))
            Toggle("換字時展開動態島", isOn: $session.expandOnChange)
            Text("背景換字時暫時展開，至少間隔 2 秒；停留與收合由 iOS 決定。")
                .font(.caption).foregroundStyle(.secondary)
            HStack {
                Button("開始背景連動", action: start).disabled(runtime.active || runtime.requesting)
                Button("停止背景連動", action: stop).disabled(!runtime.active && !runtime.requesting && !session.active)
            }
            Text(runtime.message).font(.footnote).foregroundStyle(runtime.active ? Color.green : Color.orange)
            if runtime.active { Text("已連動 \(runtime.elapsedMinutes) 分鐘 · 無固定時限").font(.caption) }
            Text(session.message).font(.footnote)
            Text(session.islandUpdateStatus).font(.caption)
            Text("提交完成不等於 iOS 已刷新畫面。動態島更新逾時與 C4 車況中斷會分開標示。")
                .font(.caption).foregroundStyle(.secondary)
            Text("先連接 C4 與屏幕，再按「開始背景連動」。等顯示「iOS 已允許」才切換 App。沒有程式設定的時間上限；仍可能因系統收回、手動停止或連續 30 秒無有效車況而結束。需要 iOS 26／Xcode 26 以上；系統結束後須回 App 再按開始。前景連動不需開始背景任務。")
                .font(.caption).foregroundStyle(.secondary)
        }
    }
}
