import Foundation
import CryptoKit
@main struct StartupTests {
    static func main() throws {
        let p = StartupPlayback(); var checks = 0
        for row in try String(contentsOfFile:"tests/startup_scenarios.csv",encoding:.utf8).split(separator:"\n") {
            let c = row.components(separatedBy:","); if c[0] == "action" { continue }
            let now = Int64(c[1])!; var result = -1
            if c[0] == "begin" { p.begin(now) }
            else if c[0] == "cancel" { p.cancel() }
            else { result = p.step(now, ready:c[2] == "1", power:c[3] == "1", interrupt:c[4] == "1", idle:c[5] == "1", nativeMode:c[6] == "1") }
            precondition(result == Int(c[7])! && p.active == (c[8] == "1"), "\(row) got \(result)/\(p.active)")
            checks += 1
        }
        let gif = try Data(contentsOf:URL(fileURLWithPath:"Resources/Startup/startup_car.gif"))
        let packet = IPixelProtocol.gif(gif)!
        let golden = try String(contentsOfFile:"tests/startup_gif.csv",encoding:.utf8).trimmingCharacters(in:.whitespacesAndNewlines).components(separatedBy:",")
        precondition(packet.prefix(15).map { String(format:"%02x",$0) }.joined() == golden[0])
        precondition(SHA256.hash(data:Data(packet)).map { String(format:"%02x",$0) }.joined() == golden[1])
        print("\(checks) shared startup transitions and upstream GIF packet passed")
    }
}
