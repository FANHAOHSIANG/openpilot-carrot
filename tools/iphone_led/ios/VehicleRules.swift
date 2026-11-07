import Foundation

/// Display-only rules. Keep parity with Android VehicleRules and its shared replay fixtures.
final class VehicleRules {
    static let hardAccel = -4.5
    static let hardMinSpeed = 20.0 / 3.6
    private var slowingSince: Int64 = -1, hardSince: Int64 = -1, releaseSince: Int64 = -1
    private var alertSince: Int64 = -1, lastSample: Int64 = -1
    private var hardSamples = 0
    private var slowing = false, hard = false
    private(set) var emergencyActive = false
    func reset() {
        slowingSince = -1; hardSince = -1; releaseSince = -1; alertSince = -1; lastSample = -1
        hardSamples = 0; slowing = false; hard = false; emergencyActive = false
    }
    private func resetEmergency() {
        hardSince = -1; releaseSince = -1; alertSince = -1; hardSamples = 0; hard = false; emergencyActive = false
    }
    func choose(speed: Double, accel: Double, brake: Bool, left: Bool, right: Bool, gear: String, now: Int64) -> String {
        guard speed.isFinite, accel.isFinite, speed >= 0, now >= 0 else { reset(); return "" }
        if lastSample >= 0 && (now <= lastSample || now-lastSample > 500) { reset() }
        lastSample = now
        let drive = gear == "drive" || gear == "d"
        if !drive { resetEmergency() }
        if slowing {
            if speed < 3.0/3.6 || accel >= -0.25 { slowing = false; slowingSince = -1 }
        } else if speed >= 5.0/3.6 && accel <= -0.5 {
            if slowingSince < 0 { slowingSince = now }
            if now-slowingSince >= 300 { slowing = true }
        } else { slowingSince = -1 }
        if drive {
            if hard {
                if accel > -2.0 || speed < 3.0/3.6 {
                    if releaseSince < 0 { releaseSince = now }
                    if now-releaseSince >= 500 { hard = false; hardSince = -1; hardSamples = 0 }
                } else { releaseSince = -1 }
            } else if speed >= Self.hardMinSpeed && accel <= Self.hardAccel {
                if hardSince < 0 { hardSince = now; hardSamples = 0 }
                hardSamples += 1
                if now-hardSince >= 300 && hardSamples >= 3 { hard = true; releaseSince = -1; alertSince = now }
            } else { hardSince = -1; hardSamples = 0 }
            emergencyActive = alertSince >= 0 && (hard || now-alertSince < 6000)
            if emergencyActive { return ((now-alertSince)/2000)%2 == 0 ? "前方塞車" : "減速中" }
            if !hard { alertSince = -1 }
        }
        if drive && (brake || slowing) { return "減速中" }
        if gear == "reverse" || gear == "r" { reset(); return "倒車" }
        if left && right { if gear == "park" || gear == "p" { return "暫停一下謝謝" }; return drive ? "謝謝" : "" }
        return left ? "左轉彎" : right ? "右轉彎" : ""
    }
}
