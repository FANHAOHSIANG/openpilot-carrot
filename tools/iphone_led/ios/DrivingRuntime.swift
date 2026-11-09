import BackgroundTasks
import CoreLocation
import SwiftUI
import UIKit

/// ActivityKit is presentation. This object owns the separate, user-initiated
/// CPU/network task. Merely requesting one does not authorize background work.
@MainActor
final class DrivingRuntime: NSObject, ObservableObject, CLLocationManagerDelegate {
    @Published var useTripLocation = UserDefaults.standard.object(forKey: "ledUseTripLocation") as? Bool ?? true {
        didSet { UserDefaults.standard.set(useTripLocation, forKey: "ledUseTripLocation") }
    }
    @Published private(set) var tripStatus = "行車定位尚未開始"
    @Published private(set) var gpsSampledAt: Date?
    private var metrics = TripMetrics()
    private var previousLocation: CLLocation?
    private let location = CLLocationManager()
    var gpsSpeedKmh: Double? { guard let gpsSampledAt, Date().timeIntervalSince(gpsSampledAt) < 15 else { return nil }; return metrics.speedKmh }
    var tripDistanceKm: Double? { active && useTripLocation ? metrics.metres / 1000 : nil }
    override init() {
        super.init()
        location.delegate = self
    }
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
        if useTripLocation { startTrip(); return }
        #if compiler(>=6.2)
        if #available(iOS 26.0, *) { submit(); return }
        #endif
        message = "此模式需要 iOS 26 與 Xcode 26 以上；目前請保持 App 在前景"
    }

    private func startTrip() {
        guard CLLocationManager.locationServicesEnabled() else { message = "請先開啟 iPhone 定位服務"; return }
        guard let modes = Bundle.main.object(forInfoDictionaryKey: "UIBackgroundModes") as? [String], modes.contains("location") else {
            message = "缺少背景定位設定，請重新產生完整專案"; return
        }
        identifier = "location." + UUID().uuidString
        requesting = true
        switch location.authorizationStatus {
        case .notDetermined:
            message = "行車里程需要定位；請允許使用 App 期間定位"
            location.requestWhenInUseAuthorization()
        case .authorizedWhenInUse, .authorizedAlways: activateTrip()
        default: finish("定位未允許；可到系統設定開啟，或關閉行車定位模式使用實驗性背景任務", success: false)
        }
    }
    private func activateTrip() {
        guard requesting, useTripLocation, UIApplication.shared.applicationState == .active else { return }
        metrics = TripMetrics(); previousLocation = nil; gpsSampledAt = nil
        location.activityType = .automotiveNavigation
        location.desiredAccuracy = kCLLocationAccuracyBest
        location.distanceFilter = kCLDistanceFilterNone
        location.pausesLocationUpdatesAutomatically = false
        location.showsBackgroundLocationIndicator = true
        location.allowsBackgroundLocationUpdates = true
        location.startUpdatingLocation()
        active = true; requesting = false; elapsedMinutes = 0
        requests = 0; backgroundRequests = 0
        budget = DriveWorkBudget(now: ProcessInfo.processInfo.systemUptime)
        message = "行車定位已開始；等待 GPS 與有效 C4 車況"
        tripStatus = "等待手機 GPS；定位僅供本次速度／里程，不上傳或儲存軌跡"
        onStarted?()
        let id = identifier
        watchdog = Task { @MainActor [weak self] in
            while !Task.isCancelled {
                do { try await Task.sleep(nanoseconds: 1_000_000_000) } catch { return }
                guard let self, self.identifier == id, self.active else { return }
                self.tick()
            }
        }
    }
    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        Task { @MainActor [weak self] in
            guard let self, self.useTripLocation, self.active || self.requesting else { return }
            switch self.location.authorizationStatus {
            case .authorizedAlways, .authorizedWhenInUse:
                if self.requesting { self.activateTrip() }
            case .denied, .restricted: self.finish("定位權限已關閉；背景行車已停止", success: false)
            default: break
            }
        }
    }
    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        Task { @MainActor [weak self] in
            guard let self, self.active, self.useTripLocation, let fix = locations.last else { return }
            let previous = self.previousLocation
            if let previous, fix.timestamp <= previous.timestamp { return }
            let accepted = self.metrics.record(speed: fix.speed, accuracy: fix.horizontalAccuracy,
                age: Date().timeIntervalSince(fix.timestamp), distance: previous.map { fix.distance(from: $0) },
                interval: previous.map { fix.timestamp.timeIntervalSince($0.timestamp) })
            guard accepted else { return }
            self.previousLocation = fix; self.gpsSampledAt = fix.timestamp
            let speed = self.metrics.speedKmh.map { String(format: "%.0f km/h", $0) } ?? "速度未知"
            self.tripStatus = String(format: "手機 GPS %@ · 本次約 %.2f km（非 C4 車速）", speed, self.metrics.metres / 1000)
        }
    }
    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        let code = (error as NSError).code
        Task { @MainActor [weak self] in
            guard let self, self.active, self.useTripLocation else { return }
            self.tripStatus = "手機定位暫不可用（\(code)）；不會拿定位代替 C4 車況"
            if code == CLError.denied.rawValue { self.finish("定位服務已中止；請回 App 確認權限", success: false) }
        }
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
        if hasVehicle {
            message = useTripLocation ? (gpsSampledAt == nil ? "已收到 C4；等待手機 GPS，請留在 App" : "行車定位與 C4 已更新，可切換 App；系統仍可能中止") : "已收到有效車況，可切換 App；背景持續性仍由 iOS 決定"
        }
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
        location.stopUpdatingLocation()
        location.allowsBackgroundLocationUpdates = false
        previousLocation = nil; gpsSampledAt = nil
        tripStatus = "行車定位已停止"
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
        if let id, !id.hasPrefix("location.") { BGTaskScheduler.shared.cancel(taskRequestWithIdentifier: id) }
        work?.setTaskCompleted(success: success)
        onEnded?()
    }
}
