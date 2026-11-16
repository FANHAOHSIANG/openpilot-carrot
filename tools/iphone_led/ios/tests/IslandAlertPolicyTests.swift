import Foundation

@main
struct IslandAlertPolicyTests {
    static func main() {
        var policy = IslandAlertPolicy()
        func expect(_ actual: Bool, _ expected: Bool, _ reason: String) {
            precondition(actual == expected, reason)
        }
        policy.reset(text: "Baby in car")
        expect(policy.shouldAlert(text: "Baby in car", eligible: true, uptime: 0), false, "No startup alert")
        expect(policy.shouldAlert(text: "左轉彎", eligible: true, uptime: 1), true, "Changed words alert")
        expect(policy.shouldAlert(text: "左轉彎", eligible: true, uptime: 1.5), false, "Same words never repeat")
        expect(policy.shouldAlert(text: "減速中", eligible: true, uptime: 2), false, "Throttle rapid switch")
        expect(policy.shouldAlert(text: "倒車，請注意", eligible: true, uptime: 2.5), false, "Keep latest switch")
        expect(policy.shouldAlert(text: "倒車，請注意", eligible: true, uptime: 3), true, "Deliver latest after throttle")
        expect(policy.shouldAlert(text: "倒車，請注意", eligible: true, uptime: 20), false, "No heartbeat alert")
        expect(policy.shouldAlert(text: "謝謝", eligible: true, uptime: 20.5), true, "Subsequent new content")
        expect(policy.shouldAlert(text: "減速中", eligible: true, uptime: 21), false, "Pending change")
        expect(policy.shouldAlert(text: "清屏", eligible: false, uptime: 21.5), false, "Clear/foreground/stale cancels pending")
        expect(policy.shouldAlert(text: "清屏", eligible: true, uptime: 24), false, "No delayed stale alert")
        expect(policy.shouldAlert(text: "左轉彎", eligible: false, uptime: 25), false, "Disabled or disconnected")
        expect(policy.shouldAlert(text: "左轉彎", eligible: true, uptime: 26), false, "No replay upon enabling/reconnect")
        policy.reset(text: "右轉彎")
        expect(policy.shouldAlert(text: "右轉彎", eligible: true, uptime: 27), false, "New activity resets baseline")
        print("14 island alert policy checks passed")
    }
}
