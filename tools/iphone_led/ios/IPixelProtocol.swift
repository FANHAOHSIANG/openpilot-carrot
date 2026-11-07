import Foundation

/// Transient slot 0, 16-row glyph strips. No erase-ROM command is used.
enum IPixelProtocol {
    static func power(_ on: Bool) -> [UInt8] { [5, 0, 7, 1, on ? 1 : 0] }
    static func ack(_ b: [UInt8]) -> Bool {
        b.count == 5 && b[0] == 5 && b[1] == 0 && [UInt8(0),1,3].contains(b[4])
    }
    static func animation(_ effect: String) -> UInt8 {
        switch effect { case "blink": return 5; case "left": return 1
        case "right": return 2; case "breathe": return 6; default: return 0 }
    }
    static func text(_ bitmap: [UInt8], width: Int, height: Int = 16,
                     rgb: [UInt8], effect: String = "static") -> [UInt8]? {
        guard height == 16, (1...2040).contains(width), rgb.count == 3,
              bitmap.count == ((width+7)/8)*16 else { return nil }
        let cols = (width+7)/8
        var data: [UInt8] = [UInt8(cols),0,1,1,animation(effect),80,effect == "rainbow" ? 1 : 0]
        data += rgb + [1,0,0,0]
        for i in 0..<cols {
            let x = effect == "right" ? cols-1-i : i
            data += [0] + rgb
            for y in 0..<16 {
                let b = bitmap[y*cols+x]
                var v: UInt8 = 0
                for bit in 0..<8 { v |= ((b >> bit) & 1) << (7-bit) }
                data.append(v)
            }
        }
        var crc: UInt32 = 0xffffffff
        for b in data {
            crc ^= UInt32(b)
            for _ in 0..<8 { crc = (crc >> 1) ^ (crc & 1 == 1 ? 0xedb88320 : 0) }
        }
        crc ^= 0xffffffff
        func le(_ n: UInt32, _ count: Int) -> [UInt8] {
            (0..<count).map { UInt8(truncatingIfNeeded: n >> ($0*8)) }
        }
        return le(UInt32(data.count+15),2) + [0,1,0] + le(UInt32(data.count),4) + le(crc,4) + [0,0] + data
    }
}
