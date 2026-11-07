import Foundation

/// Existing LOY drawing commands with optional transparent-row trimming.
/// Compact commands must follow a clear; zero bits are not assumed to erase pixels.
enum LoyBitmap {
    private static func word(_ value: Int) -> [UInt8] {
        [UInt8(value & 255), UInt8((value >> 8) & 255)]
    }
    private static func draw(_ data: [UInt8]) -> [UInt8] {
        if data.count < 128 { return [0x32, UInt8(data.count)] + data }
        if data.count < 256 { return [0x32, 0x81, UInt8(data.count)] + data }
        return [0x32, 0x82] + word(data.count) + data
    }
    static func pixels(_ packed: [UInt8], width: Int, height: Int, color: [UInt8], compact: Bool = false) -> [[UInt8]] {
        guard width > 0, width <= 256, height > 0, height <= 64, color.count == 3 else { return [] }
        let row = (width + 7) / 8, step = max(1, 240 / row)
        guard packed.count == row * height else { return [] }
        func empty(_ y: Int) -> Bool { !packed[(y * row)..<((y + 1) * row)].contains { $0 != 0 } }
        var first = 0, last = height
        if compact {
            while first < last && empty(first) { first += 1 }
            while last > first && empty(last - 1) { last -= 1 }
        }
        var commands: [[UInt8]] = []
        for y in stride(from: first, to: last, by: step) {
            let end = min(last, y + step)
            let header = [UInt8(0)] + color + word(0) + word(y) + word(width - 1) + word(end - 1)
            commands.append(draw(header + Array(packed[(y * row)..<(end * row)])))
        }
        return commands
    }
}
