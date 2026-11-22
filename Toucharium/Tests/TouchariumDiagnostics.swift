// SPDX-License-Identifier: GPL-2.0-or-later

import CoreImage
import CoreVideo
import Foundation
import Testing
import UIKit
@testable import Kernarium

private final class DiagnosticFrame: @unchecked Sendable {
    private let lock = NSLock()
    private var buffer: CVPixelBuffer?

    func receive(_ image: CVPixelBuffer) {
        lock.withLock { if buffer == nil { buffer = image } }
    }

    var image: CVPixelBuffer? { lock.withLock { buffer } }
}

/// Opt-in hosted-test control of a guest through a loopback harness. This
/// code is absent from the application target and never runs on normal launch.
@MainActor
enum TouchariumDiagnostics {
    private struct Command: Decodable {
        let action: String
        let text: String?
        let x: Int32?
        let y: Int32?
        let pressed: Int32?
    }

    static func run(endpoint: String, seconds: Double) async throws {
        let base = try #require(URL(string: endpoint))
        try #require(base.scheme == "http" && base.host == "localhost")
        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = 3
        configuration.timeoutIntervalForResource = 5
        let session = URLSession(configuration: configuration)
        defer { session.invalidateAndCancel() }
        let deadline = ContinuousClock.now + .seconds(seconds)
        while ContinuousClock.now < deadline {
            do {
                let (data, _) = try await session.data(
                    from: base.appendingPathComponent("command")
                )
                for command in try JSONDecoder().decode([Command].self, from: data) {
                    switch command.action {
                    case "console":
                        let bytes = Data((command.text ?? "").utf8)
                        let result = bytes.withUnsafeBytes {
                            guard let buffer = $0.baseAddress else { return Int32(0) }
                            return kernarium_runtime_loader_send_console_input(
                                buffer, $0.count
                            )
                        }
                        print("TOUCHARIUM_CONSOLE_RESULT:\(result)")
                    case "touch":
                        let x = try #require(command.x)
                        let y = try #require(command.y)
                        try #require((0...32767).contains(x) && (0...32767).contains(y))
                        kernarium_runtime_loader_send_touch(0, UInt32(x), UInt32(y),
                            command.pressed == 1 ? 1 : 0)
                    case "frame":
                        let png = try await captureFrame()
                        var request = URLRequest(url: base.appendingPathComponent("frame"))
                        request.httpMethod = "POST"
                        request.setValue("image/png", forHTTPHeaderField: "Content-Type")
                        request.httpBody = png
                        let (_, response) = try await session.data(for: request)
                        try #require((response as? HTTPURLResponse)?.statusCode == 200)
                    default:
                        throw NSError(domain: "TouchariumDiagnostics", code: 1)
                    }
                    print("TOUCHARIUM_DIAGNOSTIC_DONE:\(command.action)")
                }
            } catch {
                print("TOUCHARIUM_DIAGNOSTIC_ERROR:\(error)")
            }
            try await Task.sleep(for: .seconds(1))
        }
    }

    private static func captureFrame() async throws -> Data {
        let capture = DiagnosticFrame()
        let result = kernarium_runtime_loader_set_frame_sink({ context, buffer in
            guard let context, let buffer else { return }
            Unmanaged<DiagnosticFrame>.fromOpaque(context).takeUnretainedValue()
                .receive(Unmanaged<CVPixelBuffer>.fromOpaque(buffer).takeUnretainedValue())
        }, Unmanaged.passUnretained(capture).toOpaque(), 4096, 1)
        defer {
            _ = kernarium_runtime_loader_set_frame_sink(nil, nil, 0, 0)
            withExtendedLifetime(capture) {}
        }
        try #require(result == 0)
        let deadline = ContinuousClock.now + .seconds(5)
        while capture.image == nil, ContinuousClock.now < deadline {
            try await Task.sleep(for: .milliseconds(100))
        }
        let buffer = try #require(capture.image)
        let image = CIImage(cvPixelBuffer: buffer)
        let cgImage = try #require(CIContext().createCGImage(image, from: image.extent))
        return try #require(UIImage(cgImage: cgImage).pngData())
    }
}
