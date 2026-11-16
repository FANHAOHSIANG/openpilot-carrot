import Foundation
@main struct VehicleRulesTests {
 static func main() throws {
  let rules = VehicleRules(); var previous = ""; var checks = 0
  for row in try String(contentsOfFile:"tests/vehicle_scenarios.csv",encoding:.utf8).split(separator:"\n") {
   let c = row.components(separatedBy:","); if c[0] == "scenario" { continue }
   if previous != c[0] { rules.reset(); previous = c[0] }
   let result = rules.choose(speed:Double(c[2])!,accel:Double(c[3])!,brake:c[4] == "1",left:c[5] == "1",right:c[6] == "1",gear:c[7],now:Int64(c[1])!)
   precondition(result == c[8] && rules.emergencyActive == (c[9] == "1"),"\(c[0]) @\(c[1]): expected \(c[8])/\(c[9]), got \(result)/\(rules.emergencyActive)")
   checks += 1
  }
  print("\(checks) shared emergency/regen/gear/stale replay samples passed")
 }
}
