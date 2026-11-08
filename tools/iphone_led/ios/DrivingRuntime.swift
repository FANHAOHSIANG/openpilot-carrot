import BackgroundTasks
import SwiftUI
import UIKit

/// ActivityKit is presentation. This object owns the separate, user-initiated
/// CPU/network task. Merely requesting one does not authorize background work.
@MainActor
final class DrivingRuntime: ObservableObject {
    @Published private(set) var active = false
    @Published private(set) var requesting = false
    @Published private(set) var message = "尚未開始；切換 App 前請啟動行車連動"
    @Published private(set) var remainingMinutes = 0
    private var identifier: String?
    private var task: BGTask?
    private var budget: DriveWorkBudget?
    private var lastProgress = -Double.infinity
    var onEnded: (() -> Void)?

    // Called ONLY by the foreground Start button, never by timers or reconnect.
    func start() {
        guard !active, !requesting, UIApplication.shared.applicationState == .active else { return }
        #if compiler(>=6.2)
        if #available(iOS 26.0, *) { submit(); return }
        #endif
        message = "此模式需要 iOS 26 與 Xcode 26 以上；目前請保持 App 在前景"
    }

    #if compiler(>=6.2)
    @available(iOS 26.0, *)
    private func submit() {
        guard let bundle = Bundle.main.bundleIdentifier else { return }
        let base = bundle + ".ledDrive"
        let permitted = Bundle.main.object(forInfoDictionaryKey: "BGTaskSchedulerPermittedIdentifiers") as? [String] ?? []
        guard permitted.contains(base + ".*") else {
            message = "專案缺少背景任務設定，請用新版 project.yml 重新產生並安裝"; return
        }
        let id = base + "." + UUID().uuidString
        identifier = id; requesting = true
        message = "正在向 iOS 申請；請留在 App 等待允許"
        // A concrete identifier avoids wildcard launch-handler matching bugs.
        let registered = BGTaskScheduler.shared.register(forTaskWithIdentifier: id, using: .main) { [weak self] incoming in
            Task { @MainActor in
                guard let self, self.identifier == id, self.requesting,
                      let work = incoming as? BGContinuedProcessingTask else {
                    incoming.setTaskCompleted(success: false); return
                }
                self.task = work
                work.expirationHandler = { [weak self] in
                    Task { @MainActor in
                        guard let self, self.identifier == id else { return }
                        self.finish("iOS 已收回背景時間或使用者已取消；請回 App 再開始", success: false)
                    }
                }
                self.budget = DriveWorkBudget(now: ProcessInfo.processInfo.systemUptime)
                self.active = true; self.requesting = false; self.remainingMinutes = 60
                self.lastProgress = -.infinity
                work.progress.totalUnitCount = 18_000 // up to 60 minutes at 5 Hz
                work.progress.completedUnitCount = 0
                self.message = "iOS 已允許行車連動，可切換 App（最多 60 分鐘）"
            }
        }
        guard registered else {
            identifier = nil; requesting = false
            message = "iOS 無法註冊背景任務；目前請保持 App 在前景"; return
        }
        do {
            let request = BGContinuedProcessingTaskRequest(identifier: id, title: "Carrot LED 行車連動",
                subtitle: "最多 60 分鐘；接收並處理 C4 車況")
            request.strategy = .fail // never leave a job queued for a later drive
            try BGTaskScheduler.shared.submit(request)
        } catch {
            finish("iOS 未允許背景連動：\(error.localizedDescription)", success: false)
            return
        }
        Task { [weak self] in
            try? await Task.sleep(nanoseconds: 10_000_000_000)
            guard let self, self.identifier == id, self.requesting else { return }
            self.finish("iOS 尚未啟動背景任務；請保持前景，稍後再試", success: false)
        }
    }
    #endif

    func receivedSample() {
        guard active else { return }
        budget?.received(now: ProcessInfo.processInfo.systemUptime)
        tick()
    }
    func tick() {
        guard active, let budget else { return }
        let now = ProcessInfo.processInfo.systemUptime
        if let end = budget.end(now: now) {
            finish(end == .duration ? "本次 60 分鐘連動已完成；請回 App 開始下一次" : "C4 已連續 30 秒無有效車況；背景任務已結束",
                   success: end == .duration && budget.samples > 0)
            return
        }
        let minutes = Int(ceil(Double(budget.remaining(now: now)) / 60))
        if remainingMinutes != minutes { remainingMinutes = minutes }
        guard now - lastProgress >= 1 else { return }; lastProgress = now
        #if compiler(>=6.2)
        if #available(iOS 26.0, *), let work = task as? BGContinuedProcessingTask {
            work.progress.completedUnitCount = budget.samples
        }
        #endif
    }
    func stop() { finish("行車連動已停止；可回到前景再次開始", success: false) }
    private func finish(_ text: String, success: Bool) {
        guard identifier != nil || active || requesting else { return }
        let id = identifier, work = task, count = budget?.samples ?? 0
        identifier = nil; task = nil; budget = nil
        active = false; requesting = false; remainingMinutes = 0; message = text
        work?.expirationHandler = nil
        #if compiler(>=6.2)
        if #available(iOS 26.0, *), success, let continued = work as? BGContinuedProcessingTask {
            // The acquisition window is complete: report only samples really processed.
            continued.progress.totalUnitCount = max(1, count)
            continued.progress.completedUnitCount = count
        }
        #endif
        if let id { BGTaskScheduler.shared.cancel(taskRequestWithIdentifier: id) }
        work?.setTaskCompleted(success: success)
        onEnded?()
    }
}
