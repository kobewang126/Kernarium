// SPDX-License-Identifier: GPL-2.0-or-later

import CryptoKit
import Dispatch
import Foundation
import Testing
@testable import Kernarium

struct TouchariumImageTests {
    @Test func cancelledImportNeverPublishes() async throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let source = directory.appendingPathComponent("source.erofs")
        let data = Data(repeating: 0, count: 8192)
        try data.write(to: source)
        let descriptor = TouchariumImageDescriptor(filename: "system.erofs", size: 8192,
            sha256: SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined(), policyVersion: 2)
        let documents = directory.appendingPathComponent("Documents")
        let gate = DispatchSemaphore(value: 0)
        let operation = Task.detached {
            gate.wait()
            return try TouchariumImage.install(from: source, descriptor: descriptor, into: documents)
        }
        operation.cancel()
        gate.signal()
        await #expect(throws: CancellationError.self) { try await operation.value }
        #expect(try FileManager.default.contentsOfDirectory(atPath: documents.path).isEmpty)
    }
    @Test func interruptedImportsDoNotAccumulateOrRemoveUserFiles() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let interrupted = directory.appendingPathComponent(".toucharium-import-\(UUID().uuidString)")
        let userFile = directory.appendingPathComponent(".toucharium-import-not-an-import")
        try Data([1]).write(to: interrupted)
        try Data([2]).write(to: userFile)
        try TouchariumImage.removeInterruptedImports(in: directory)
        #expect(!FileManager.default.fileExists(atPath: interrupted.path))
        #expect(try Data(contentsOf: userFile) == Data([2]))
    }
    @Test func verifiedImportAndChangedImageDetection() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let source = directory.appendingPathComponent("source.erofs")
        let data = Data(repeating: 0x65, count: 8192)
        try data.write(to: source)
        let descriptor = TouchariumImageDescriptor(filename: "system.erofs", size: Int64(data.count),
            sha256: SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined(), policyVersion: 2)
        let documents = directory.appendingPathComponent("Documents")
        #expect(!TouchariumImage.isInstalled(descriptor, in: documents))
        let image = try TouchariumImage.install(from: source, descriptor: descriptor, into: documents)
        #expect(try Data(contentsOf: image) == data)
        #expect(TouchariumImage.isInstalled(descriptor, in: documents))
        try Data([0]).write(to: image)
        #expect(!TouchariumImage.isInstalled(descriptor, in: documents))
        _ = try TouchariumImage.install(from: source, descriptor: descriptor, into: documents)
        #expect(TouchariumImage.isInstalled(descriptor, in: documents))
    }

    @Test func rejectedImportPreservesExistingImageAndGuestData() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let source = directory.appendingPathComponent("source.erofs")
        let documents = directory.appendingPathComponent("Documents")
        try FileManager.default.createDirectory(at: documents, withIntermediateDirectories: true)
        let existing = documents.appendingPathComponent("system.erofs")
        try Data("old image".utf8).write(to: existing)
        let overlay = documents.appendingPathComponent("overlay.ext4")
        try Data("user data".utf8).write(to: overlay)
        try Data(repeating: 0, count: 8192).write(to: source)
        let descriptor = TouchariumImageDescriptor(filename: "system.erofs", size: 8192,
                                                   sha256: String(repeating: "f", count: 64), policyVersion: 2)
        #expect(throws: TouchariumImageError.self) {
            try TouchariumImage.install(from: source, descriptor: descriptor, into: documents)
        }
        #expect(try Data(contentsOf: existing) == Data("old image".utf8))
        #expect(try Data(contentsOf: overlay) == Data("user data".utf8))
        #expect(!FileManager.default.fileExists(atPath: TouchariumImage.receiptURL(in: documents).path))
        #expect(try FileManager.default.contentsOfDirectory(atPath: documents.path).sorted() ==
                ["overlay.ext4", "system.erofs"])
    }
}
