// SPDX-License-Identifier: GPL-2.0-or-later

import CryptoKit
import Dispatch
import Foundation
import Testing
@testable import Kernarium

struct TouchariumImageTests {
    private func imageData(_ fill: UInt8) -> Data {
        var data = Data(repeating: fill, count: 8192)
        data.replaceSubrange(1024..<1028, with: [0xe2, 0xe1, 0xf5, 0xe0])
        data[1036] = 12
        return data
    }

    private func describe(_ data: Data, filename: String = "user-built.erofs",
                          policy: Int = 2) -> TouchariumImageDescriptor {
        TouchariumImageDescriptor(filename: filename, size: Int64(data.count),
            sha256: SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined(),
            policyVersion: policy)
    }

    @Test func externalDescriptorsAcceptIndependentImagesAndRejectInvalidMetadata() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let file = directory.appendingPathComponent("local.erofs.import.json")
        for fill: UInt8 in [1, 2] {
            let descriptor = describe(imageData(fill), filename: "local-\(fill).erofs")
            try JSONEncoder().encode(descriptor).write(to: file)
            #expect(try TouchariumImageDescriptor.load(from: file) == descriptor)
            let source = directory.appendingPathComponent(descriptor.filename)
            try imageData(fill).write(to: source)
            let destination = try TouchariumImage.install(from: source, descriptor: descriptor,
                into: directory.appendingPathComponent("Documents"))
            #expect(TouchariumImageDescriptor.validFilename(destination.lastPathComponent))
            #expect(TouchariumImage.installation(in: destination.deletingLastPathComponent())?.descriptor == descriptor)
        }
        for filename in ["../outside.erofs", "/outside.erofs", "nested/file.erofs", "bad\\file.erofs", ".hidden.erofs"] {
            let descriptor = describe(imageData(0), filename: filename)
            #expect(throws: TouchariumImageError.self) { try descriptor.validated() }
            #expect(!TouchariumImage.isInstalled(descriptor, in: directory))
        }
        #expect(throws: TouchariumImageError.self) { try describe(imageData(0), policy: 3).validated() }
        let invalid = TouchariumImageDescriptor(filename: "local.erofs", size: 8192,
            sha256: String(repeating: "g", count: 64), policyVersion: 2)
        #expect(throws: TouchariumImageError.self) { try invalid.validated() }
        try Data(repeating: 32, count: 65537).write(to: file)
        #expect(throws: TouchariumImageError.self) { try TouchariumImageDescriptor.load(from: file) }
    }

    @Test func receiptPublicationFailureKeepsPreviousImageAndData() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let source = directory.appendingPathComponent("local.erofs")
        let documents = directory.appendingPathComponent("Documents")
        try imageData(3).write(to: source)
        let original = describe(imageData(3))
        let installed = try TouchariumImage.install(from: source, descriptor: original, into: documents)
        let receipt = TouchariumImage.receiptURL(in: documents)
        let oldReceipt = try Data(contentsOf: receipt)
        let overlay = receipt.deletingLastPathComponent().appendingPathComponent("overlay.ext4")
        try Data("guest data".utf8).write(to: overlay)
        try imageData(4).write(to: source)
        let replacement = describe(imageData(4))
        // Make receipt publication fail after copying: an atomic write cannot
        // replace a directory, while the old image remains untouched.
        try FileManager.default.removeItem(at: receipt)
        try FileManager.default.createDirectory(at: receipt, withIntermediateDirectories: true)
        #expect(throws: (any Error).self) {
            try TouchariumImage.install(from: source, descriptor: replacement, into: documents)
        }
        #expect(try Data(contentsOf: installed) == imageData(3))
        #expect(try Data(contentsOf: overlay) == Data("guest data".utf8))
        #expect(try FileManager.default.contentsOfDirectory(atPath: documents.path).sorted() ==
            [TouchariumImage.installedFilename, "UbuntuTouch"].sorted())
        try FileManager.default.removeItem(at: receipt)
        try oldReceipt.write(to: receipt)
        #expect(TouchariumImage.isInstalled(original, in: documents))
        let destination = try TouchariumImage.install(from: source, descriptor: replacement, into: documents)
        #expect(destination != installed)
        #expect(!FileManager.default.fileExists(atPath: installed.path))
        #expect(TouchariumImage.installation(in: documents)?.descriptor == replacement)
        #expect(try Data(contentsOf: overlay) == Data("guest data".utf8))
        let orphan = documents.appendingPathComponent("TouchariumSystem-\(UUID().uuidString).erofs")
        try Data([1]).write(to: orphan)
        try TouchariumImage.removeInterruptedImports(in: documents)
        #expect(!FileManager.default.fileExists(atPath: orphan.path))
        #expect(FileManager.default.fileExists(atPath: destination.path))
        #expect(TouchariumImage.installation(in: documents)?.descriptor == replacement)
    }

    @Test func freshDataDeletesPreviousDataOnlyAfterSuccessfulPublication() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let source = directory.appendingPathComponent("local.erofs")
        let documents = directory.appendingPathComponent("Documents")
        let original = describe(imageData(1))
        try imageData(1).write(to: source)
        _ = try TouchariumImage.install(from: source, descriptor: original, into: documents)
        let oldData = documents.appendingPathComponent("UbuntuTouch")
        let marker = oldData.appendingPathComponent("user-data")
        try Data("important".utf8).write(to: marker)
        let wrong = describe(imageData(2))
        #expect(throws: TouchariumImageError.self) {
            try TouchariumImage.install(from: source, descriptor: wrong, into: documents, preserveData: false)
        }
        #expect(try Data(contentsOf: marker) == Data("important".utf8))
        _ = try TouchariumImage.install(from: source, descriptor: original, into: documents, preserveData: false)
        let fresh = try #require(TouchariumImage.installation(in: documents))
        #expect(fresh.dataDirectory != "UbuntuTouch")
        #expect(!FileManager.default.fileExists(atPath: marker.path))
        #expect(try FileManager.default.contentsOfDirectory(atPath: oldData.path) == ["imported-image.json"])
        let freshDirectory = documents.appendingPathComponent(fresh.dataDirectory)
        let newMarker = freshDirectory.appendingPathComponent("new-data")
        try Data("new data".utf8).write(to: newMarker)
        _ = try TouchariumImage.install(from: source, descriptor: original, into: documents)
        #expect(TouchariumImage.installation(in: documents)?.dataDirectory == fresh.dataDirectory)
        #expect(try Data(contentsOf: newMarker) == Data("new data".utf8))
        // Simulate an interrupted deletion and verify that startup finishes it.
        var receipt = try #require(JSONSerialization.jsonObject(with: Data(contentsOf:
            TouchariumImage.receiptURL(in: documents))) as? [String: Any])
        let nextDataName = "TouchariumData-\(UUID().uuidString)"
        try FileManager.default.createDirectory(at: documents.appendingPathComponent(nextDataName),
                                               withIntermediateDirectories: false)
        receipt["dataDirectory"] = nextDataName
        receipt["retiredDataDirectory"] = fresh.dataDirectory
        try JSONSerialization.data(withJSONObject: receipt).write(to: TouchariumImage.receiptURL(in: documents))
        try TouchariumImage.removeInterruptedImports(in: documents)
        #expect(!FileManager.default.fileExists(atPath: freshDirectory.path))
        #expect(TouchariumImage.installation(in: documents)?.dataDirectory == nextDataName)
    }

    @Test @MainActor func replacementRequiresStoppedGuestAndSurvivesRelaunch() async throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let suite = "TouchariumImageTests-\(UUID().uuidString)"
        let defaults = try #require(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let source = directory.appendingPathComponent("local.erofs")
        let data = imageData(5)
        try data.write(to: source)
        _ = try TouchariumImage.install(from: source, descriptor: describe(data), into: directory)
        let description = directory.appendingPathComponent("local.erofs.import.json")
        try JSONEncoder().encode(describe(data)).write(to: description)
        let store = TouchariumImageStore(directory: directory, defaults: defaults)
        #expect(store.ready)
        await store.beginReplacement {
            #expect(store.stopping)
            #expect(store.replacing)
            store.importImages([source, description])
            #expect(store.progress == nil)
            return false
        }
        #expect(store.stopFailed)
        store.importImages([source, description])
        #expect(store.progress == nil)
        let reopened = TouchariumImageStore(directory: directory, defaults: defaults)
        #expect(reopened.replacing && !reopened.stopping && !reopened.stopFailed)
        reopened.keepCurrentImage()
        #expect(reopened.needsRelaunch)
        #expect(TouchariumImageStore(directory: directory, defaults: defaults).ready)
        #expect(!TouchariumImageStore(directory: directory, defaults: defaults).replacing)
        let retry = TouchariumImageStore(directory: directory, defaults: defaults)
        await retry.beginReplacement { true }
        retry.importImages([source, description])
        let clock = ContinuousClock()
        let deadline = clock.now.advanced(by: .seconds(5))
        while retry.progress != nil && clock.now < deadline {
            try await Task.sleep(for: .milliseconds(20))
        }
        #expect(retry.progress == nil)
        #expect(retry.error == nil)
        #expect(retry.needsRelaunch && !retry.replacing)
        let nextLaunch = TouchariumImageStore(directory: directory, defaults: defaults)
        #expect(nextLaunch.ready && !nextLaunch.replacing && !nextLaunch.needsRelaunch)
        #expect(nextLaunch.filename == retry.filename)
    }

    @Test func legacyReceiptPreservesExistingInstallation() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let name = "previous-version.erofs"
        let data = imageData(7)
        let descriptor = describe(data, filename: name)
        let image = directory.appendingPathComponent(name)
        try data.write(to: image)
        let modified = try #require(image.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate)
        let receipt = TouchariumImage.receiptURL(in: directory)
        try FileManager.default.createDirectory(at: receipt.deletingLastPathComponent(), withIntermediateDirectories: true)
        let oldReceipt: [String: Any] = ["sha256": descriptor.sha256, "size": data.count,
                                       "modified": modified.timeIntervalSinceReferenceDate]
        try JSONSerialization.data(withJSONObject: oldReceipt).write(to: receipt)
        let installed = TouchariumImage.installation(in: directory, legacyFilename: name)
        #expect(installed?.filename == name)
        #expect(installed?.descriptor == descriptor)
        #expect(TouchariumImage.installation(in: directory, legacyFilename: "../outside.erofs") == nil)
    }

    @Test func matchingChecksumCannotAdmitWrongImageFormat() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let source = directory.appendingPathComponent("wrong.erofs")
        let data = Data(repeating: 0, count: 8192)
        try data.write(to: source)
        #expect(throws: TouchariumImageError.self) {
            try TouchariumImage.install(from: source, descriptor: describe(data),
                into: directory.appendingPathComponent("Documents"))
        }
        #expect(TouchariumImage.installation(in: directory.appendingPathComponent("Documents")) == nil)
    }

    @Test func cancelledImportNeverPublishes() async throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let source = directory.appendingPathComponent("source.erofs")
        let data = imageData(0)
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
        let data = imageData(0x65)
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
        let existing = documents.appendingPathComponent(TouchariumImage.installedFilename)
        try Data("old image".utf8).write(to: existing)
        let overlay = documents.appendingPathComponent("overlay.ext4")
        try Data("user data".utf8).write(to: overlay)
        try imageData(0).write(to: source)
        let descriptor = TouchariumImageDescriptor(filename: "system.erofs", size: 8192,
                                                   sha256: String(repeating: "f", count: 64), policyVersion: 2)
        #expect(throws: TouchariumImageError.self) {
            try TouchariumImage.install(from: source, descriptor: descriptor, into: documents)
        }
        #expect(try Data(contentsOf: existing) == Data("old image".utf8))
        #expect(try Data(contentsOf: overlay) == Data("user data".utf8))
        #expect(!FileManager.default.fileExists(atPath: TouchariumImage.receiptURL(in: documents).path))
        #expect(try FileManager.default.contentsOfDirectory(atPath: documents.path).sorted() ==
                [TouchariumImage.installedFilename, "overlay.ext4"].sorted())
    }
}
