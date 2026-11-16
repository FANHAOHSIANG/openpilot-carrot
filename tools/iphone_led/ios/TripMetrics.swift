import Foundation

/// GPS is used only for the user's visible trip meter, never as C4 carState.
struct TripMetrics {
    private(set) var metres = 0.0
    private(set) var speedKmh: Double?
    mutating func record(speed: Double, accuracy: Double, age: Double, distance: Double?, interval: Double?) -> Bool {
        guard accuracy.isFinite, accuracy >= 0, accuracy <= 50, age.isFinite, age >= -1, age <= 10 else { return false }
        speedKmh = speed.isFinite && speed >= 0 && speed <= 80 ? speed * 3.6 : nil
        if let distance, let interval, accuracy <= 30, speed >= 1, speed <= 80,
           interval > 0, interval <= 10, distance.isFinite,
           distance >= max(3, accuracy * 0.5), distance / interval <= 80 {
            metres += distance
        }
        return true
    }
}
