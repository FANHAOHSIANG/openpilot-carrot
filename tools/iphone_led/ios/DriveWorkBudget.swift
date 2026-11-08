import Foundation

/// One user-started acquisition session with no app-imposed duration limit.
/// Bridge liveness is separate from vehicle-data freshness. A real response
/// without carState may keep the session open, but never validates a vehicle sample.
struct DriveWorkBudget {
    enum End: Equatable { case disconnected, invalidClock }
    static let reconnectGrace: Double = 300
    let startedAt: Double
    private(set) var samples: Int64 = 0
    private(set) var responses: Int64 = 0
    private(set) var lastSample: Double
    private(set) var lastResponse: Double
    private(set) var lastResponseHasVehicle = false
    init(now: Double) {
        startedAt = now; lastSample = now; lastResponse = now
    }
    mutating func received(now: Double) {
        receivedResponse(hasVehicle: true, now: now)
    }
    mutating func receivedResponse(hasVehicle: Bool, now: Double) {
        guard now.isFinite, now >= lastResponse, end(now: now) == nil else { return }
        // Invalidation takes effect even if two replies arrive close enough
        // to coalesce their progress count after a variable network delay.
        if !hasVehicle { lastResponseHasVehicle = false }
        // The bridge polls at 5 Hz; duplicate callbacks cannot inflate progress.
        guard responses == 0 || now - lastResponse >= 0.15 else { return }
        responses += 1; lastResponse = now; lastResponseHasVehicle = hasVehicle
        if hasVehicle { samples += 1; lastSample = now }
    }
    func end(now: Double) -> End? {
        if !now.isFinite || now < lastResponse { return .invalidClock }
        if now - lastResponse >= Self.reconnectGrace { return .disconnected }
        return nil
    }
    func hasRecentResponse(now: Double) -> Bool {
        responses > 0 && now >= lastResponse && now - lastResponse < 0.9
    }
    func hasFreshVehicle(now: Double) -> Bool {
        samples > 0 && lastResponseHasVehicle && now >= lastSample && now - lastSample < 0.9
    }
    func elapsedMinutes(now: Double) -> Int {
        guard now.isFinite, now >= startedAt else { return 0 }
        return Int((now - startedAt) / 60)
    }
    func reportProgress(_ progress: Progress) {
        // The user decides when the stream ends, so its total is unknown.
        // Do not invent a target, elapsed-time percentage, or recurring deadline.
        progress.totalUnitCount = -1
        progress.completedUnitCount = responses
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
