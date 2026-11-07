import Foundation
@main struct IPixelTests {
 static func main() {
  // Same upstream golden vectors used by Android; asymmetric pixels.
  let expected = ["450000010036000000c936cd7b00000200010100500012abef010000000012abef0153287a154f3c610b5826751f42316b0012abefa5f79cc1b3e886d5affc91cbb8e68ddf","4500000100360000003f42ab8200000200010105500012abef010000000012abef0153287a154f3c610b5826751f42316b0012abefa5f79cc1b3e886d5affc91cbb8e68ddf","450000010036000000382ffcff00000200010101500012abef010000000012abef0153287a154f3c610b5826751f42316b0012abefa5f79cc1b3e886d5affc91cbb8e68ddf","4500000100360000007df5119b00000200010102500012abef010000000012abefa5f79cc1b3e886d5affc91cbb8e68ddf0012abef0153287a154f3c610b5826751f42316b","4500000100360000006d6e89d500000200010106500012abef010000000012abef0153287a154f3c610b5826751f42316b0012abefa5f79cc1b3e886d5affc91cbb8e68ddf","45000001003600000015da7c4600000200010100500112abef010000000012abef0153287a154f3c610b5826751f42316b0012abefa5f79cc1b3e886d5affc91cbb8e68ddf"]
  let bitmap = (0..<32).map { UInt8(truncatingIfNeeded:$0*37+128) }
  let effects=["static","blink","left","right","breathe","rainbow"]
  for (i,effect) in effects.enumerated() {
   let frame=IPixelProtocol.text(bitmap,width:16,rgb:[0x12,0xab,0xef],effect:effect)!
   precondition(frame.map { String(format:"%02x",$0) }.joined()==expected[i],"upstream golden frame \(effect)")
  }
  let blank=IPixelProtocol.text([UInt8](repeating:0,count:128),width:64,rgb:[0,0,0])!
  precondition(blank.count==189 && blank[14]==0 && blank[15]==8)
  precondition(blank.dropFirst(29).allSatisfy { $0==0 })
  precondition(IPixelProtocol.power(false)==[5,0,7,1,0])
  precondition(IPixelProtocol.ack([5,0,0,1,3]) && !IPixelProtocol.ack([5,0,0,1,2]) && !IPixelProtocol.ack([]))
  precondition(IPixelProtocol.text([],width:64,height:32,rgb:[0,0,0])==nil)
  precondition(IPixelProtocol.text([],width:2041,rgb:[0,0,0])==nil)
  precondition(IPixelProtocol.text([UInt8](repeating:0,count:4080),width:2040,rgb:[0,0,0])!.count==5129)
  print("iPixel upstream golden vectors and clear/power/ACK/bounds checks passed")
 }
}
