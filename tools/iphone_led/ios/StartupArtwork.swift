import Foundation

enum StartupArtwork {
    static let colors: [[UInt8]] = [[0,0,0],[255,126,0],[93,224,20],[255,211,0]]
    private static var cache = [Int: [UInt8]]()
    static func supported(width: Int, height: Int) -> Bool { height == 16 && [64,96].contains(width) }
    static func gif() -> Data? {
        guard let url = Bundle.main.url(forResource: "startup_car", withExtension: "gif") else { return nil }
        return try? Data(contentsOf: url)
    }
    static func layers(width: Int, frame: Int) -> [[UInt8]]? {
        guard [64,96].contains(width), (0..<48).contains(frame) else { return nil }
        if cache[width] == nil {
            guard let url = Bundle.main.url(forResource: "startup\(width)", withExtension: "bin"),
                  let data = try? Data(contentsOf: url), data.count == width*16*48 else { return nil }
            cache[width] = Array(data)
        }
        guard let data = cache[width] else { return nil }
        let row = (width+7)/8
        var layers = [[UInt8]](repeating: [UInt8](repeating:0,count:row*16), count:4)
        for y in 0..<16 { for x in 0..<width {
            let color = Int(data[frame*width*16+y*width+x])
            guard color < 4 else { return nil }
            if color > 0 { layers[color][y*row+x/8] |= UInt8(128 >> (x%8)) }
        } }
        return layers
    }
}
