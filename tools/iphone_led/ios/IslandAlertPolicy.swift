import Foundation

// No timers or per-animation-frame alerts. Coalesce rapid changes to the latest text.
struct IslandAlertPolicy {
    private var previousText: String?
    private var pendingText: String?
    private var lastAlertTime = -Double.infinity

    mutating func reset(text: String) {
        previousText = text
        pendingText = nil
        lastAlertTime = -Double.infinity
    }

    mutating func shouldAlert(text: String, eligible: Bool, uptime: TimeInterval) -> Bool {
        let changed = previousText != nil && previousText != text
        previousText = text
        guard eligible else { pendingText = nil; return false }
        if changed { pendingText = text }
        guard pendingText == text, uptime - lastAlertTime >= 2 else { return false }
        pendingText = nil
        lastAlertTime = uptime
        return true
    }
}
