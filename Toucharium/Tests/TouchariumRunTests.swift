// SPDX-License-Identifier: GPL-2.0-or-later

import Foundation
import CryptoKit
import Testing
@testable import Kernarium

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
            let image = temporary.appendingPathExtension("erofs")
            try FileManager.default.moveItem(at: temporary, to: image)
            defer { try? FileManager.default.removeItem(at: image) }
            let descriptionSource = try #require(
                ProcessInfo.processInfo.environment["TOUCHARIUM_IMAGE_DESCRIPTOR_URL"])
            let descriptionURL = try #require(URL(string: descriptionSource))
            let (descriptionData, descriptionResponse) = try await session.data(from: descriptionURL)
            try #require((descriptionResponse as? HTTPURLResponse)?.statusCode == 200)
            let descriptionFile = temporary.appendingPathExtension("import.json")
            try descriptionData.write(to: descriptionFile)
            defer { try? FileManager.default.removeItem(at: descriptionFile) }
            let descriptor = try TouchariumImageDescriptor.load(from: descriptionFile)
            let destination = try TouchariumImage.install(
                from: image, descriptor: descriptor, into: documents
            )
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
