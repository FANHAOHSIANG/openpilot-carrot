import Foundation

/// A submitted-canvas estimate, not a readback of the physical panel.
/// Uses the existing live-draw bitmap command. Zero bits are transparent;
/// pixels that become black are explicitly painted black. Several TLVs may
/// share a bounded frame, reducing BLE writes without changing animation time.
final class LoyCanvas {
    private var previous: [UInt32] = []
    private var size: (Int, Int) = (0, 0)
    private var refreshedAt: Double = -.infinity

    func reset() {
        previous = []; size = (0, 0); refreshedAt = -.infinity
    }

    func update(_ canvas: [UInt32], width: Int, height: Int, now: Double, batch: Bool = true) -> [[UInt8]] {
        guard (8...256).contains(width), (8...64).contains(height),
              canvas.count == width * height, now.isFinite else { reset(); return [] }
        let full = size.0 != width || size.1 != height || previous.count != canvas.count
            || now < refreshedAt || now - refreshedAt >= 2
        var masks: [UInt32: [UInt8]] = [:]
        let row = (width + 7) / 8
        for i in canvas.indices {
            let color = canvas[i] & 0xffffff
            if !full && color == previous[i] { continue }
            if masks[color] == nil { masks[color] = [UInt8](repeating: 0, count: row * height) }
            let x = i % width, y = i / width
            masks[color]![y * row + x / 8] |= UInt8(128 >> (x % 8))
        }
        // New colors first, erased pixels last: never blank the entire panel
        // between two pictures. Periodic complete coverage repairs missed data.
        let colors = masks.keys.filter { $0 != 0 }.sorted() + (masks[0] == nil ? [] : [UInt32(0)])
        var commands: [[UInt8]] = []
        for color in colors {
            commands += Self.rectangles(masks[color]!, width: width, height: height, color: color)
        }
        previous = canvas.map { $0 & 0xffffff }; size = (width, height)
        if full { refreshedAt = now }
        if !batch { return commands }
        var packets: [[UInt8]] = [], packet: [UInt8] = []
        for command in commands {
            if packet.count + command.count > 960 {
                packets.append(packet); packet = []
            }
            packet += command
        }
        if !packet.isEmpty { packets.append(packet) }
        return packets
    }

    static func ackStatus(_ data: [UInt8]) -> Int? {
        guard data.count == 13, data[0] == 0xaa, data[1] == 0x55,
              data[4] == 7, data[5] == 0, data[8] == 0x81, data[9] == 0x82 else { return nil }
        let checksum = data.prefix(11).reduce(0) { $0 + Int($1) } & 65535
        guard checksum == Int(data[11]) | (Int(data[12]) << 8) else { return nil }
        return Int(data[10])
    }

    private static func word(_ n: Int) -> [UInt8] { [UInt8(n & 255), UInt8((n >> 8) & 255)] }
    private static func command(_ bits: [UInt8], row: Int, x0: Int, x1: Int,
                                y0: Int, y1: Int, width: Int, color: UInt32) -> [UInt8] {
        var data: [UInt8] = [0, UInt8((color >> 16) & 255), UInt8((color >> 8) & 255), UInt8(color & 255)]
        data += word(x0 * 8) + word(y0) + word(min(width - 1, x1 * 8 + 7)) + word(y1)
        for y in y0...y1 { data += bits[(y * row + x0)...(y * row + x1)] }
        return (data.count < 128 ? [0x32, UInt8(data.count)] : [0x32, 0x81, UInt8(data.count)]) + data
    }
    private static func rectangles(_ bits: [UInt8], width: Int, height: Int, color: UInt32) -> [[UInt8]] {
        let row = (width + 7) / 8
        var x0 = row, x1 = -1, y0 = height, y1 = -1
        for y in 0..<height { for x in 0..<row where bits[y * row + x] != 0 {
            x0 = min(x0, x); x1 = max(x1, x); y0 = min(y0, y); y1 = max(y1, y)
        } }
        guard x1 >= x0 else { return [] }
        let rowsPerCommand = max(1, 240 / (x1 - x0 + 1))
        var boxed: [[UInt8]] = []
        for y in stride(from: y0, through: y1, by: rowsPerCommand) {
            boxed.append(command(bits, row: row, x0: x0, x1: x1, y0: y,
                                 y1: min(y1, y + rowsPerCommand - 1), width: width, color: color))
        }
        // Sparse changes on distant rows can be cheaper as individual bands.
        var bands: [[UInt8]] = []
        var y = y0
        while y <= y1 {
            var left = row, right = -1
            for x in 0..<row where bits[y * row + x] != 0 { left = min(left, x); right = max(right, x) }
            if right >= left {
                bands.append(command(bits, row: row, x0: left, x1: right, y0: y, y1: y, width: width, color: color))
            }
            y += 1
        }
        return bands.reduce(0, { $0 + $1.count }) < boxed.reduce(0, { $0 + $1.count }) ? bands : boxed
    }
}
