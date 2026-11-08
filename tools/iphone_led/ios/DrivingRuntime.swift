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
    @Published private(set) var elapsedMinutes = 0
    @Published private(set) var connectionStatus = ""
    @Published private(set) var diagnostic = ""
    private var requests = 0
    private var backgroundRequests = 0
    private var watchdog: Task<Void, Never>?
    var onStarted: (() -> Void)?
    private var identifier: String?
    private var task: BGTask?
    private var budget: DriveWorkBudget?
    private var lastProgress = -Double.infinity
    private var lastTitleUpdate = -Double.infinity
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
                self.active = true; self.requesting = false; self.elapsedMinutes = 0
                self.connectionStatus = "等待下一筆 C4 回覆"
                self.lastProgress = -.infinity; self.lastTitleUpdate = -.infinity
                self.budget?.reportProgress(work.progress)
                self.message = "背景任務已啟動；請留在 App 等待有效車況"
                self.requests = 0; self.backgroundRequests = 0; self.diagnostic = "尚未發出請求"
                self.onStarted?()
                self.watchdog = Task { @MainActor [weak self] in
                    while !Task.isCancelled {
                        do { try await Task.sleep(nanoseconds: 1_000_000_000) } catch { return }
                        guard let self, self.identifier == id, self.active else { return }
                        self.tick()
                    }
                }
            }
        }
        guard registered else {
            identifier = nil; requesting = false
            message = "iOS 無法註冊背景任務；目前請保持 App 在前景"; return
        }
        do {
            let request = BGContinuedProcessingTaskRequest(identifier: id, title: "Carrot LED 行車連動",
                subtitle: "持續接收 C4 車況；可隨時停止")
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

    func requestStarted(background: Bool) {
        guard active else { return }
        requests += 1
        if background { backgroundRequests += 1 }
    }
    func requestFailed(_ reason: String) {
        guard active else { return }
        diagnostic = "請求 \(requests)／背景 \(backgroundRequests)：\(reason)"
    }
    func receivedSample() {
        receivedBridgeResponse(hasVehicle: true)
    }
    func receivedBridgeResponse(hasVehicle: Bool) {
        guard active else { return }
        diagnostic = "請求 \(requests)／背景 \(backgroundRequests)：" + (hasVehicle ? "收到有效車況" : "橋接回覆 valid=false")
        if hasVehicle { message = "已收到有效車況，可切換 App；背景持續性仍由 iOS 決定" }
        budget?.receivedResponse(hasVehicle: hasVehicle, now: ProcessInfo.processInfo.systemUptime)
        tick()
    }
    func tick() {
        guard active, let budget else { return }
        let now = ProcessInfo.processInfo.systemUptime
        if let end = budget.end(now: now) {
            finish(end == .invalidClock ? "連動計時狀態異常；請回 App 再開始" : "C4 已連續 5 分鐘無橋接回覆；背景任務已結束",
                   success: false)
            return
        }
        let minutes = budget.elapsedMinutes(now: now)
        if elapsedMinutes != minutes { elapsedMinutes = minutes }
        let status = budget.hasFreshVehicle(now: now) ? "C4 車況持續更新" : budget.hasRecentResponse(now: now)
            ? "C4 心跳正常，等待有效車況；過期車況不顯示" : "C4 回覆中斷，正在重試（最多等待 5 分鐘）"
        if connectionStatus != status { connectionStatus = status }
        guard now - lastProgress >= 1 else { return }; lastProgress = now
        #if compiler(>=6.2)
        if #available(iOS 26.0, *), let work = task as? BGContinuedProcessingTask {
            budget.reportProgress(work.progress)
            if now - lastTitleUpdate >= 30 {
                lastTitleUpdate = now
                work.updateTitle("Carrot LED 行車連動", subtitle: "橋接回覆 \(budget.responses) 筆／有效車況 \(budget.samples) 筆；\(minutes) 分鐘")
            }
        }
        #endif
    }
    func stop() { finish("背景連動已停止；前景車況仍可使用", success: active && (budget?.responses ?? 0) > 0) }
    private func finish(_ text: String, success: Bool) {
        guard identifier != nil || active || requesting else { return }
        let id = identifier, work = task, count = budget?.responses ?? 0
        watchdog?.cancel(); watchdog = nil
        identifier = nil; task = nil; budget = nil
        active = false; requesting = false; elapsedMinutes = 0; message = text
        connectionStatus = ""
        work?.expirationHandler = nil
        #if compiler(>=6.2)
        if #available(iOS 26.0, *), success, let continued = work as? BGContinuedProcessingTask {
            // The user ended the session: the actual response total is now known.
            continued.progress.totalUnitCount = max(1, count)
            continued.progress.completedUnitCount = count
        }
        #endif
        if let id { BGTaskScheduler.shared.cancel(taskRequestWithIdentifier: id) }
        work?.setTaskCompleted(success: success)
        onEnded?()
    }
}
