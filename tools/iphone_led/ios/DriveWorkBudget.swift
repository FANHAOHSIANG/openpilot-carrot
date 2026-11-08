import Foundation

/// One user-started acquisition session. No automatic renewal, no synthetic work.
struct DriveWorkBudget {
    enum End: Equatable { case duration, disconnected }
    let startedAt: Double
    let duration: Double
    private(set) var samples: Int64 = 0
    private(set) var lastSample: Double
    init(now: Double, duration: Double = 3600) {
        startedAt = now; lastSample = now; self.duration = duration
    }
    mutating func received(now: Double) {
        guard now.isFinite, now >= lastSample, end(now: now) == nil else { return }
        // The bridge polls at 5 Hz; duplicate callbacks cannot inflate progress.
        guard samples == 0 || now - lastSample >= 0.15 else { return }
        samples += 1; lastSample = now
    }
    func end(now: Double) -> End? {
        if !now.isFinite || now < startedAt || now - startedAt >= duration { return .duration }
        if now - lastSample >= 30 { return .disconnected }
        return nil
    }
    func remaining(now: Double) -> Int { max(0, Int(ceil(duration - max(0, now - startedAt)))) }
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
