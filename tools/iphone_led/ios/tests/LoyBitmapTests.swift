import Foundation
@main struct LoyBitmapTests {
    static var checks = 0
    static func check(_ value: Bool, _ reason: String) { precondition(value, reason); checks += 1 }
    static func word(_ a: [UInt8], _ i: Int) -> Int { Int(a[i]) | (Int(a[i+1]) << 8) }
    static func roundTrip(_ bits: [UInt8], _ w: Int, _ h: Int) {
        var rendered = [UInt8](repeating: 0, count: bits.count)
        let stride = (w+7)/8
        for cmd in LoyBitmap.pixels(bits,width:w,height:h,color:[0x12,0x34,0x56],compact:true) {
            check(cmd[0] == 0x32, "draw opcode")
            var n = Int(cmd[1]), start = 2
            if n == 0x81 { n = Int(cmd[2]); start = 3 }
            else if n == 0x82 { n = word(cmd,2); start = 4 }
            check(cmd.count == start+n && n <= 252,"bounded complete command")
            check(Array(cmd[start..<(start+4)]) == [0,0x12,0x34,0x56],"color preserved")
            let x0 = word(cmd,start+4), y0 = word(cmd,start+6), x1 = word(cmd,start+8), y1 = word(cmd,start+10)
            check(x0 == 0 && x1 == w-1 && y0 >= 0 && y1 >= y0 && y1 < h,"original coordinates")
            check(n-12 == (y1-y0+1)*stride,"row alignment")
            rendered.replaceSubrange((y0*stride)..<((y1+1)*stride),with:cmd[(start+12)...])
        }
        check(bits == rendered,"compact screen differs from full canvas")
    }
    static func main() throws {
        for w in [8,64,96,97,256] { for h in [8,16,64] {
            let stride = (w+7)/8
            var bits = [UInt8](repeating:0,count:stride*h)
            roundTrip(bits,w,h)
            check(LoyBitmap.pixels(bits,width:w,height:h,color:[0,0,0],compact:true).isEmpty,"empty layer omitted")
            for row in [0,h/2,h-1] {
                bits = [UInt8](repeating:0,count:stride*h); bits[row*stride] = 128
                roundTrip(bits,w,h)
            }
            for i in bits.indices { bits[i] = UInt8((i*73+19)&255) }
            roundTrip(bits,w,h)
        } }
        var band = [UInt8](repeating:0,count:192)
        for i in (4*12)..<(12*12) { band[i] = 255 }; roundTrip(band,96,16)
        let original = LoyBitmap.pixels(band,width:96,height:16,color:[0,0,0])[0].count+12
        let compact = LoyBitmap.pixels(band,width:96,height:16,color:[0,0,0],compact:true)[0].count+12
        check(original == 219 && compact == 122,"96x16 byte budget")
        for w in [64,96] {
            let art = [UInt8](try Data(contentsOf:URL(fileURLWithPath:"Resources/Startup/startup\(w).bin")))
            for frame in 0..<48 { for color in 1..<4 {
                var layer = [UInt8](repeating:0,count:w/8*16)
                for y in 0..<16 { for x in 0..<w {
                    if art[frame*w*16+y*w+x] == UInt8(color) { layer[y*(w/8)+x/8] |= UInt8(128 >> (x%8)) }
                } }
                roundTrip(layer,w,16)
            } }
        }
        check(LoyBitmap.pixels([0],width:96,height:16,color:[0,0,0],compact:true).isEmpty,"invalid length")
        print("\(checks) LOY compact encoding, canvas equivalence and startup asset checks passed")
    }
}
