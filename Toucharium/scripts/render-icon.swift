// SPDX-License-Identifier: GPL-2.0-or-later
// Raster counterpart of Branding/Toucharium.svg; App Store icons are opaque.
import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

let size = 1024
let context = CGContext(
    data: nil, width: size, height: size, bitsPerComponent: 8,
    bytesPerRow: size * 4, space: CGColorSpaceCreateDeviceRGB(),
    bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue
)!
context.translateBy(x: 0, y: CGFloat(size))
context.scaleBy(x: 1, y: -1)
func color(_ r: CGFloat, _ g: CGFloat, _ b: CGFloat) -> CGColor {
    CGColor(colorSpace: CGColorSpaceCreateDeviceRGB(), components: [r / 255, g / 255, b / 255, 1])!
}
let charcoal = color(28, 37, 35)
let ivory = color(244, 240, 230)
let orange = color(255, 121, 79)
func rounded(_ rect: CGRect, _ radius: CGFloat, _ fill: CGColor) {
    context.setFillColor(fill)
    context.addPath(CGPath(roundedRect: rect, cornerWidth: radius, cornerHeight: radius, transform: nil))
    context.fillPath()
}
context.setFillColor(charcoal)
context.fill(CGRect(x: 0, y: 0, width: size, height: size))
context.setStrokeColor(ivory)
context.setLineWidth(32)
context.addPath(CGPath(roundedRect: CGRect(x: 234, y: 226, width: 556, height: 572), cornerWidth: 98, cornerHeight: 98, transform: nil))
context.strokePath()
rounded(CGRect(x: 332, y: 352, width: 360, height: 96), 24, orange)
context.setFillColor(orange)
context.move(to: CGPoint(x: 464, y: 428))
context.addLine(to: CGPoint(x: 560, y: 428))
context.addLine(to: CGPoint(x: 560, y: 666))
context.addQuadCurve(to: CGPoint(x: 536, y: 690), control: CGPoint(x: 560, y: 690))
context.addLine(to: CGPoint(x: 488, y: 690))
context.addQuadCurve(to: CGPoint(x: 464, y: 666), control: CGPoint(x: 464, y: 690))
context.closePath()
context.fillPath()
rounded(CGRect(x: 678, y: 670, width: 150, height: 158), 28, charcoal)
rounded(CGRect(x: 710, y: 704, width: 104, height: 104), 28, orange)
let output = URL(fileURLWithPath: CommandLine.arguments.dropFirst().first ?? "Toucharium/Sources/Assets.xcassets/TouchariumIcon.appiconset/TouchariumIcon.png")
let image = context.makeImage()!
let destination = CGImageDestinationCreateWithURL(output as CFURL, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(destination, image, nil)
guard CGImageDestinationFinalize(destination) else { fatalError("Cannot write app icon") }
print("Wrote opaque 1024 x 1024 Toucharium icon")
