import ActivityKit
import Foundation

struct LEDActivityAttributes: ActivityAttributes {
    struct ContentState: Codable, Hashable {
        var sampledAt: Date
        var fresh: Bool
        var screenConnected: Bool
        var automatic: Bool
        // Optional so an existing activity payload without text remains decodable.
        var displayText: String?
        var gpsSpeedKmh: Double?
        var tripDistanceKm: Double?
        var gpsSampledAt: Date?
    }
    var title: String
}
