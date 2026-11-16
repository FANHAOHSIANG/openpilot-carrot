import Foundation

/// Original monochrome pixel eyes. The selected RGB color is applied by the transport.
enum EyesBitmap {
    static func make(width: Int, height: Int, variant: Int, phase: Int) -> [UInt8] {
        guard width > 0, height > 0, width <= 256, height <= 64 else { return [] }
        let stride = (width+7)/8
        var bits = [UInt8](repeating: 0, count: stride*height)
        let tick = max(0,phase)
        let blink = tick%18 == 16
        let look = variant == 1 ? [0,0,-3,-3,0,3,3,0][(tick/2)%8] : 0
        for y in 0..<height { for x in 0..<width {
            let px = Double(x)*64/Double(width), py = Double(y)*16/Double(height)
            let side = px < 32 ? 0 : 1
            let u = px-Double(side == 0 ? 16 : 48), v = py-8
            guard abs(u) < 14 else { continue }
            let curve = 5*pow(max(0,1-abs(u)/14),0.6)
            var inside = abs(v) <= curve
            if variant == 2 { inside = inside && v >= -3+0.22*(side == 0 ? u : -u) }
            if blink { inside = abs(v) < 1 && abs(u) < 12 }
            let pupil = pow((u-Double(look))/2.5,2)+pow(v/3.5,2) < 1
            let highlight = abs(u-Double(look)+1) < 1.2 && abs(v+2) < 1
            if inside && (blink || !pupil || highlight) { bits[y*stride+x/8] |= UInt8(128 >> (x%8)) }
        } }
        return bits
    }
}
