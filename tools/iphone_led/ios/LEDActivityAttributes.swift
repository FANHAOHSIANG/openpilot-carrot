import ActivityKit
import Foundation

struct LEDActivityAttributes: ActivityAttributes {
    struct ContentState: Codable, Hashable {
        var sampledAt: Date
        var fresh: Bool
        var screenConnected: Bool
        var automatic: Bool
    }
    var title: String
}
