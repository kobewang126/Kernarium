// SPDX-License-Identifier: GPL-2.0-or-later

import Foundation
import CryptoKit
import Testing

/// A Designed for iPad launch ends with its hosted test run. This opt-in
/// harness keeps the application alive for a bounded interactive guest run.
struct TouchariumRunTests {
    @Test func holdApplicationForGuestRun() async throws {
        let documents = try FileManager.default.url(
            for: .documentDirectory, in: .userDomainMask,
            appropriateFor: nil, create: true
        )
        print("TOUCHARIUM_DOCUMENTS:\(documents.path)")
        if let source = ProcessInfo.processInfo.environment[
            "TOUCHARIUM_IMAGE_URL"
        ] {
            let url = try #require(URL(string: source))
            let configuration = URLSessionConfiguration.ephemeral
            configuration.timeoutIntervalForRequest = 30
            configuration.timeoutIntervalForResource = 600
            let session = URLSession(configuration: configuration)
            defer { session.invalidateAndCancel() }
            let (temporary, response) = try await session.download(from: url)
            try #require((response as? HTTPURLResponse)?.statusCode == 200)
            let destination = documents.appendingPathComponent(
                "ubuntu-touch-pdk-470-r2.erofs"
            )
            let existing = FileManager.default.fileExists(atPath: destination.path)
            let image = existing ? destination : temporary
            let file = try FileHandle(forReadingFrom: image)
            defer { try? file.close() }
            var digest = SHA256()
            while let chunk = try file.read(upToCount: 4 << 20), !chunk.isEmpty {
                digest.update(data: chunk)
            }
            let fingerprint = digest.finalize().map {
                String(format: "%02x", $0)
            }.joined()
            try #require(fingerprint ==
                "e156ff638bd6317096e321b7c8f8a59260b9065559a65218057611b861bb4244")
            if !existing {
                try FileManager.default.moveItem(at: temporary, to: destination)
            }
            print("TOUCHARIUM_IMAGE_STAGED:\(destination.path)")
            return
        }
        guard let value = ProcessInfo.processInfo.environment[
            "TOUCHARIUM_HOLD_SECONDS"
        ], let seconds = Double(value), seconds.isFinite,
           seconds > 0, seconds <= 86_400 else { return }
        if let endpoint = ProcessInfo.processInfo.environment[
            "TOUCHARIUM_DIAGNOSTIC_URL"
        ] {
            try await TouchariumDiagnostics.run(endpoint: endpoint, seconds: seconds)
            return
        }
        try await Task.sleep(for: .seconds(seconds))
    }
}
