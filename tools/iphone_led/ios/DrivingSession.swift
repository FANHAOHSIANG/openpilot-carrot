import ActivityKit
import SwiftUI
import UIKit

// A Live Activity improves Bluetooth privileges on iOS 26+, not general CPU or
// LAN execution. This is an explicitly started experiment, never a keepalive hack.
@MainActor
final class DrivingSession: ObservableObject {
    @Published private(set) var active = false
    @Published private(set) var message = "尚未開始行車即時動態"
    private var activity: Activity<LEDActivityAttributes>?
    private var observer: Task<Void, Never>?
    private var lastUpdate = Date.distantPast
    private var lastState: LEDActivityAttributes.ContentState?
    var onEnded: (() -> Void)?

    init() {
        // Never revive an old session or its stale vehicle status after relaunch.
        let orphans = Activity<LEDActivityAttributes>.activities
        Task { for item in orphans { await item.end(nil, dismissalPolicy: .immediate) } }
    }

    func start(sampledAt: Date, connected: Bool, automatic: Bool) {
        guard !active else { return }
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
                                                       screenConnected: connected, automatic: automatic)
        do {
            let item = try Activity.request(attributes: LEDActivityAttributes(title: "Carrot 行車連動"),
                content: ActivityContent(state: state, staleDate: sampledAt.addingTimeInterval(0.9)), pushType: nil)
            activity = item; active = true; lastState = state; lastUpdate = .distantPast
            message = "行車即時動態已開始；背景連動仍需實測"
            observer = Task { [weak self] in
                for await state in item.activityStateUpdates {
                    guard !Task.isCancelled else { return }
                    if state == .ended || state == .dismissed {
                        guard let self, self.activity?.id == item.id else { return }
                        self.activity = nil; self.active = false
                        self.message = "行車即時動態已結束，請回 App 重新開始"
                        self.onEnded?()
                        return
                    }
                }
            }
        } catch { message = "無法開始即時動態：\(error.localizedDescription)" }
    }

    func update(sampledAt: Date, connected: Bool, automatic: Bool) {
        guard let item = activity, active else { return }
        let now = Date()
        let fresh = now.timeIntervalSince(sampledAt) < 0.9
        let state = LEDActivityAttributes.ContentState(sampledAt: sampledAt, fresh: fresh,
                                                       screenConnected: connected, automatic: automatic)
        let changed = lastState?.fresh != fresh || lastState?.screenConnected != connected || lastState?.automatic != automatic
        // Avoid sending every 5 Hz vehicle packet to ActivityKit. A conservative
        // staleDate can show expired between updates; never extend freshness.
        guard changed || now.timeIntervalSince(lastUpdate) >= 1 else { return }
        lastState = state; lastUpdate = now
        Task { await item.update(ActivityContent(state: state, staleDate: sampledAt.addingTimeInterval(0.9))) }
    }

    func stop() {
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
            Text("背景行車連動（測試）").font(.headline)
            HStack {
                Button("開始行車即時動態", action: start).disabled(session.active)
                Button("結束") { session.stop() }.disabled(!session.active)
            }
            Text(session.message).font(.footnote)
            Text("切換 App 前先開始。即時動態不保證背景網路或動畫持續；資料過期會標示失效，App 能執行時才可嘗試清屏。")
                .font(.caption).foregroundStyle(.secondary)
        }
    }
}
