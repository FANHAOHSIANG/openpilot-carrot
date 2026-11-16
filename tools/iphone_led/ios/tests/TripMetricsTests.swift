import Foundation
@main struct Tests {
 static func main() {
  var m=TripMetrics()
  precondition(m.record(speed:10,accuracy:5,age:0,distance:nil,interval:nil))
  precondition(m.speedKmh==36 && m.metres==0)
  precondition(m.record(speed:10,accuracy:5,age:0,distance:10,interval:1))
  precondition(m.metres==10)
  _ = m.record(speed:0,accuracy:5,age:0,distance:5,interval:1)
  _ = m.record(speed:10,accuracy:5,age:0,distance:1000,interval:1)
  precondition(m.metres==10)
  precondition(!m.record(speed:10,accuracy:5,age:11,distance:10,interval:1))
  precondition(!m.record(speed:10,accuracy:100,age:0,distance:10,interval:1))
  _ = m.record(speed:-1,accuracy:5,age:0,distance:10,interval:1)
  precondition(m.speedKmh==nil && m.metres==10)
  print("Trip metrics: stale fixes, poor accuracy, jitter and jumps rejected")
 }
}
