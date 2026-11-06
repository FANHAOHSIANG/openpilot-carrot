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
    private var nextAutoAttempt = Date.distantPast
    private var cleanupComplete = false
    private var activity: Activity<LEDActivityAttributes>?
    private var observer: Task<Void, Never>?
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
        else { message = "等待 C4 車況與屏幕連線，會自動啟動背景連動" }
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
                content: ActivityContent(state: state, staleDate: sampledAt.addingTimeInterval(0.9)), pushType: nil)
            activity = item; active = true; lastState = state; lastUpdate = .distantPast
            message = "行車即時動態已開始，可切換至背景"
            observer = Task { [weak self] in
                for await state in item.activityStateUpdates {
                    guard !Task.isCancelled else { return }
                    if state == .ended || state == .dismissed {
                        guard let self, self.activity?.id == item.id else { return }
                        self.activity = nil; self.active = false
                        self.autoStart = false
                        UserDefaults.standard.set(false, forKey: "ledAutoBackground")
                        self.message = "行車即時動態已結束；自動啟動已關閉，可回 App 重新開啟"
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
        let changed = lastState?.fresh != fresh || lastState?.screenConnected != connected || lastState?.automatic != automatic || lastState?.displayText != displayText
        // Avoid sending every 5 Hz vehicle packet to ActivityKit. A conservative
        // staleDate can show expired between updates; never extend freshness.
        guard changed || now.timeIntervalSince(lastUpdate) >= 1 else { return }
        lastState = state; lastUpdate = now
        Task { await item.update(ActivityContent(state: state, staleDate: sampledAt.addingTimeInterval(0.9))) }
    }

    func stop() {
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
    let start: () -> Void
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("背景行車連動").font(.headline)
            Toggle("自動啟動背景連動", isOn: Binding(get: { session.autoStart }, set: { session.setAutoStart($0) }))
            HStack {
                Button("立即啟動", action: start).disabled(session.active)
                Button("停止並關閉自動啟動") { session.stop() }.disabled(!session.active && !session.autoStart)
            }
            Text(session.message).font(.footnote)
            Text("開啟 App，等 C4 車況與屏幕連線就緒，即會自動啟動；顯示已開始後可切換 App。這不是開機自啟或強制關閉後重啟。背景執行仍受 iOS 管理。")
                .font(.caption).foregroundStyle(.secondary)
        }
    }
}
