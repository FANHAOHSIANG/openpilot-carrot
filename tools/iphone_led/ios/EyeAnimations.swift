import Foundation
import UIKit
import ImageIO

/// The same original, indexed GIF assets are bundled by Android and iPhone.
enum EyeAnimations {
    static let files = ["crystal","gaze","devil","spiral","flame","mecha","sasuke_sharingan","sasuke_rinnegan"]
    static let names = ["晶亮眨眼","靈動眼","惡魔眼","螺旋眼","火焰眼","機甲眼","寫輪眼 → 萬花筒","萬花筒 → 輪迴眼"]
    static let displayOrder = [6,7,0,1,2,3,4,5]
    static func index(_ value: Int) -> Int { max(0,min(files.count-1,value)) }
    private static var cache: [String:Data] = [:]
    static func gif(_ variant: Int, color: UInt32) -> Data? {
        let variant = index(variant), key = "\(index(variant)):\(color)"
        if let cached = cache[key] { return cached }
        guard let url = Bundle.main.url(forResource: files[variant], withExtension: "gif"),
              let source = try? Data(contentsOf: url) else { return nil }
        var data = [UInt8](source)
        guard data.count >= 61, data.count <= 8192, data[10]&0x87 == 0x83 else { return nil }
        // Character transformations keep their original red/purple palette.
        if variant < 6 { for i in 0..<16 { for channel in 0..<3 {
            let base = Int((color >> (16-channel*8))&255)
            let value = i <= 10 ? base*i/10 : base+(255-base)*(i-10)/5
            data[13+i*3+channel] = UInt8(value)
        } } }
        if cache.count >= 24 { cache.removeAll() }
        let result = Data(data); cache[key] = result; return result
    }
    private static var images: [String:UIImage] = [:]
    static func image(_ variant: Int, color: UInt32) -> UIImage? {
        let key = "\(variant):\(color)"
        if let image = images[key] { return image }
        guard let data = gif(variant,color:color), let source = CGImageSourceCreateWithData(data as CFData,nil) else { return nil }
        var frames: [UIImage] = []
        for i in 0..<CGImageSourceGetCount(source) {
            guard let cg = CGImageSourceCreateImageAtIndex(source,i,nil) else { continue }
            let properties = CGImageSourceCopyPropertiesAtIndex(source,i,nil) as? [String:Any]
            let gif = properties?[kCGImagePropertyGIFDictionary as String] as? [String:Any]
            let duration = gif?[kCGImagePropertyGIFUnclampedDelayTime as String] as? Double
                ?? gif?[kCGImagePropertyGIFDelayTime as String] as? Double ?? 0.05
            // UIKit gives all images the same duration; expand merged idle frames.
            frames += Array(repeating:UIImage(cgImage:cg),count:max(1,Int((duration/0.05).rounded())))
        }
        guard !frames.isEmpty, let image = UIImage.animatedImage(with:frames,duration:Double(frames.count)*0.05) else { return nil }
        if images.count >= 24 { images.removeAll() }; images[key] = image; return image
    }
    static func raster(_ variant: Int, color: UInt32, width: Int, height: Int, time: Double) -> [UInt8]? {
        guard let animation = image(variant,color:color), let frames = animation.images,
              let cg = frames[Int(max(0,time)*20)%frames.count].cgImage else { return nil }
        var rgb = [UInt8](repeating:0,count:width*height*4)
        let ok = rgb.withUnsafeMutableBytes { raw -> Bool in
            guard let ctx = CGContext(data:raw.baseAddress,width:width,height:height,bitsPerComponent:8,bytesPerRow:width*4,
                space:CGColorSpaceCreateDeviceRGB(),bitmapInfo:CGImageAlphaInfo.premultipliedLast.rawValue) else { return false }
            ctx.interpolationQuality = .none
            ctx.draw(cg,in:CGRect(x:0,y:0,width:width,height:height));return true
        }
        return ok ? rgb : nil
    }
}
