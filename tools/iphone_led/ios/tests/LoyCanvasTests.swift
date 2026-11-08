import Foundation
@main struct LoyCanvasTests {
    static var checks = 0
    static func check(_ value: Bool, _ reason: String) { precondition(value, reason); checks += 1 }
    static func word(_ a: [UInt8], _ i: Int) -> Int { Int(a[i]) | Int(a[i+1]) << 8 }
    // Independent emulation of the panel's transparent bitmap operation.
    static func apply(_ packets: [[UInt8]], to canvas: inout [UInt32], w: Int, h: Int) {
        for packet in packets {
            check(!packet.isEmpty && packet.count <= 960, "bounded packet")
            var at = 0
            while at < packet.count {
                check(packet[at] == 0x32, "only live bitmap TLVs")
                var n = Int(packet[at+1]); at += 2
                if n == 0x81 { n = Int(packet[at]); at += 1 }
                else if n == 0x82 { n = word(packet, at); at += 2 }
                check(at + n <= packet.count && n >= 13 && n <= 252, "complete bounded bitmap")
                check(packet[at] == 0, "no whole-screen clear rectangle")
                let color = UInt32(packet[at+1]) << 16 | UInt32(packet[at+2]) << 8 | UInt32(packet[at+3])
                let x0 = word(packet, at+4), y0 = word(packet, at+6), x1 = word(packet, at+8), y1 = word(packet, at+10)
                check(x0 >= 0 && x1 >= x0 && x1 < w && y0 >= 0 && y1 >= y0 && y1 < h, "bounds")
                let row = (x1 - x0 + 8) / 8
                check(n == 12 + row * (y1 - y0 + 1), "row alignment")
                for y in y0...y1 { for x in x0...x1 {
                    if packet[at+12+(y-y0)*row+(x-x0)/8] & UInt8(128 >> ((x-x0)%8)) != 0 {
                        canvas[y*w+x] = color
                    }
                } }
                at += n
            }
            check(at == packet.count, "whole TLVs only")
        }
    }
    static func cost(_ packets: [[UInt8]]) -> Int { packets.reduce(0) { $0 + $1.count + 12 } }
    static func writes(_ packets: [[UInt8]], mtu: Int) -> Int { packets.reduce(0) { $0 + ($1.count + 12 + mtu - 1) / mtu } }
    static func baseline(_ canvas: [UInt32], w: Int, h: Int) -> [[UInt8]] {
        var out: [[UInt8]] = [[UInt8](repeating:0,count:15)] // previous clear command
        for color in Set(canvas).filter({ $0 != 0 }).sorted() {
            var bits = [UInt8](repeating:0,count:((w+7)/8)*h)
            for i in canvas.indices where canvas[i] == color { bits[(i/w)*((w+7)/8)+(i%w)/8] |= UInt8(128 >> (i%w%8)) }
            out += LoyBitmap.pixels(bits,width:w,height:h,color:[UInt8((color>>16)&255),UInt8((color>>8)&255),UInt8(color&255)],compact:true)
        }
        return out
    }
    static func main() throws {
        let encoder = LoyCanvas()
        for w in [8,64,96,97,256] { for h in [8,16,64] {
            encoder.reset()
            var actual = [UInt32](repeating:0xaabbcc,count:w*h)
            var target = [UInt32](repeating:0,count:w*h)
            for f in 0..<15 {
                for i in target.indices { target[i] = (i*73+f*17)%13 < 3 ? [UInt32(0xff0000),0x00ff00,0x0000ff][(i+f)%3] : 0 }
                apply(encoder.update(target,width:w,height:h,now:Double(f)/20),to:&actual,w:w,h:h)
                check(actual == target,"frame differs after palette/motion update")
                check(encoder.update(target,width:w,height:h,now:Double(f)/20+0.001).isEmpty,"duplicate frame suppressed")
            }
            // Lost data must heal after the two-second refresh, without a blank frame.
            actual[0] = 0xabcdef
            apply(encoder.update(target,width:w,height:h,now:3),to:&actual,w:w,h:h)
            check(actual == target,"full coverage repairs drift")
            encoder.reset(); actual = [UInt32](repeating:0xffffff,count:w*h)
            apply(encoder.update(target,width:w,height:h,now:3.1,batch:false),to:&actual,w:w,h:h)
            check(actual == target,"unbatched fallback after reconnect/rejection")
            target = [UInt32](repeating:0,count:w*h)
            apply(encoder.update(target,width:w,height:h,now:3.2),to:&actual,w:w,h:h)
            check(actual == target,"explicit black erases all old pixels")
        } }
        let palette: [UInt32] = [0,0xff7e00,0x5de014,0xffd300]
        for w in [64,96] {
            let source = [UInt8](try Data(contentsOf:URL(fileURLWithPath:"Resources/Startup/startup\(w).bin")))
            var oldBytes=0,newBytes=0,oldWrites=0,newWrites=0
            encoder.reset(); var actual = [UInt32](repeating:0xffffff,count:w*16)
            for f in 0..<48 {
                let target = source[(f*w*16)..<((f+1)*w*16)].map { palette[Int($0)] }
                let before = baseline(target,w:w,h:16)
                let after = encoder.update(target,width:w,height:16,now:Double(f)/20)
                oldBytes += cost(before); newBytes += cost(after)
                oldWrites += writes(before,mtu:180); newWrites += writes(after,mtu:244)
                apply(after,to:&actual,w:w,h:16)
                check(actual == target,"opening artwork reconstructed exactly")
            }
            check(newBytes < oldBytes && newWrites < oldWrites,"actual opening transfer reduction")
            print("startup \(w)x16: bytes \(oldBytes) -> \(newBytes); BLE writes \(oldWrites) -> \(newWrites)")
            // Busy-link skipping uses the last submitted canvas, not the skipped frame.
            encoder.reset(); actual = [UInt32](repeating:0xffffff,count:w*16)
            for f in [0,1,6,7,23,47] {
                let target = source[(f*w*16)..<((f+1)*w*16)].map { palette[Int($0)] }
                apply(encoder.update(target,width:w,height:16,now:Double(f)/20),to:&actual,w:w,h:16)
                check(actual == target,"skipping frames leaves no trails")
            }
        }
        check(encoder.update([0],width:96,height:16,now:0).isEmpty,"invalid buffer rejected")
        var ack: [UInt8] = [0xaa,0x55,0xff,0xff,7,0,9,0,0x81,0x82,3]
        let sum = ack.reduce(0) { $0+Int($1) }; ack += [UInt8(sum&255),UInt8(sum>>8)]
        check(LoyCanvas.ackStatus(ack) == 3,"negative ACK decoded")
        ack[11] ^= 1
        check(LoyCanvas.ackStatus(ack) == nil,"corrupt ACK ignored")
        print("\(checks) LOY delta, batch, recovery and complete-canvas checks passed")
    }
}
