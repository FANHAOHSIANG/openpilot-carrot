import Foundation
@main struct EyesTests {
    static func count(_ bits: [UInt8]) -> Int { bits.reduce(0) { $0+$1.nonzeroBitCount } }
    static func main() {
        for width in [64,96,97] { for mode in 0..<3 {
            let open=EyesBitmap.make(width:width,height:16,variant:mode,phase:0)
            let blink=EyesBitmap.make(width:width,height:16,variant:mode,phase:16)
            precondition(open.count==((width+7)/8)*16)
            precondition(count(open)>count(blink) && count(blink)>0)
            if width%8 != 0 { for y in 0..<16 { precondition(open[(y+1)*((width+7)/8)-1]&0x7f==0) } }
        } }
        precondition(EyesBitmap.make(width:64,height:16,variant:1,phase:0) != EyesBitmap.make(width:64,height:16,variant:1,phase:4))
        precondition(EyesBitmap.make(width:0,height:16,variant:0,phase:0).isEmpty)
        print("Eyes geometry and animation checks passed")
    }
}
