import Foundation

/// Same one-shot state machine as Android. No delayed callback can restart it.
final class StartupPlayback {
    static let none = -1, wait = -2, native = -3, durationMs: Int64 = 2400
    private(set) var active = false
    private var requested: Int64 = 0, started: Int64 = -1
    private var awaitingDelivery = false
    private var lastFrame = -1
    func begin(_ now: Int64) { active = true; requested = now; started = -1; awaitingDelivery = false; lastFrame = -1 }
    func cancel() { active = false; awaitingDelivery = false }
    func step(_ now: Int64, ready: Bool, power: Bool, interrupt: Bool, idle: Bool, nativeMode: Bool) -> Int {
        guard active else { return Self.none }
        if !ready || !power || interrupt || now < requested || now-requested >= 12000 {
            cancel(); return Self.none
        }
        if awaitingDelivery {
            guard idle else { return Self.wait }
            awaitingDelivery = false; started = now
        }
        if started < 0 {
            guard idle else { return Self.wait }
            started = now
            if nativeMode { awaitingDelivery = true; return Self.native }
        }
        let elapsed = now-started
        if elapsed >= Self.durationMs { cancel(); return Self.none }
        guard !nativeMode, idle else { return Self.wait }
        let frame = Int(elapsed/200)*4
        guard frame != lastFrame else { return Self.wait }
        lastFrame = frame; return frame
    }
}
