import Foundation

/// One user-started acquisition session with no app-imposed duration limit.
/// System expiration and loss of real samples still end the session.
struct DriveWorkBudget {
    enum End: Equatable { case disconnected, invalidClock }
    let startedAt: Double
    private(set) var samples: Int64 = 0
    private(set) var lastSample: Double
    init(now: Double) {
        startedAt = now; lastSample = now
    }
    mutating func received(now: Double) {
        guard now.isFinite, now >= lastSample, end(now: now) == nil else { return }
        // The bridge polls at 5 Hz; duplicate callbacks cannot inflate progress.
        guard samples == 0 || now - lastSample >= 0.15 else { return }
        samples += 1; lastSample = now
    }
    func end(now: Double) -> End? {
        if !now.isFinite || now < lastSample { return .invalidClock }
        if now - lastSample >= 30 { return .disconnected }
        return nil
    }
    func elapsedMinutes(now: Double) -> Int {
        guard now.isFinite, now >= startedAt else { return 0 }
        return Int((now - startedAt) / 60)
    }
    func reportProgress(_ progress: Progress) {
        // The user decides when the stream ends, so its total is unknown.
        // Do not invent a target, elapsed-time percentage, or recurring deadline.
        progress.totalUnitCount = -1
        progress.completedUnitCount = samples
    }
}

/// A stale URLSession completion must not release a newer in-flight request.
struct PollLease {
    private(set) var ticket: UUID?
    private var beganAt = 0.0
    mutating func begin(now: Double) -> UUID? {
        guard ticket == nil || now - beganAt >= 2 || now < beganAt else { return nil }
        let next = UUID(); ticket = next; beganAt = now; return next
    }
    mutating func finish(_ value: UUID) { if ticket == value { ticket = nil } }
    mutating func reset() { ticket = nil }
}
