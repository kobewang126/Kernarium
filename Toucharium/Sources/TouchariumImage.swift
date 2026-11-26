// SPDX-License-Identifier: GPL-2.0-or-later

import CryptoKit
import Foundation

nonisolated struct TouchariumImageDescriptor: Codable, Sendable {
    let filename: String
    let size: Int64
    let sha256: String
    let policyVersion: Int

    static func load(bundle: Bundle = .main) throws -> Self {
        guard let url = bundle.url(forResource: "TouchariumImage", withExtension: "json") else {
            throw TouchariumImageError.missingDescriptor
        }
        let value = try JSONDecoder().decode(Self.self, from: Data(contentsOf: url))
        guard value.policyVersion == 2, value.size > 1024,
              value.filename == (value.filename as NSString).lastPathComponent,
              value.filename.hasSuffix(".erofs"),
              value.sha256.count == 64, value.sha256.allSatisfy({ $0.isHexDigit }) else {
            throw TouchariumImageError.missingDescriptor
        }
        return value
    }
}

nonisolated enum TouchariumImageError: LocalizedError {
    case missingDescriptor, unsupportedImage, insufficientSpace

    var errorDescription: String? {
        switch self {
        case .missingDescriptor: "The supported system image information is missing."
        case .unsupportedImage: "This is not the supported Toucharium 2 system image. Choose the complete .erofs file."
        case .insufficientSpace: "There is not enough free storage to import this system image."
        }
    }
}

nonisolated enum TouchariumImage {
    private struct Receipt: Codable {
        let sha256: String
        let size: Int64
        let modified: Date
    }

    static func receiptURL(in directory: URL) -> URL {
        directory.appendingPathComponent("UbuntuTouch/imported-image.json")
    }

    static func removeInterruptedImports(in directory: URL) throws {
        let manager = FileManager.default
        guard manager.fileExists(atPath: directory.path) else { return }
        for url in try manager.contentsOfDirectory(at: directory, includingPropertiesForKeys: [.isRegularFileKey]) {
            let prefix = ".toucharium-import-"
            guard url.lastPathComponent.hasPrefix(prefix),
                  UUID(uuidString: String(url.lastPathComponent.dropFirst(prefix.count))) != nil,
                  try url.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile == true else { continue }
            try manager.removeItem(at: url)
        }
    }

    static func isInstalled(_ descriptor: TouchariumImageDescriptor, in directory: URL) -> Bool {
        let image = directory.appendingPathComponent(descriptor.filename)
        guard let data = try? Data(contentsOf: receiptURL(in: directory)),
              let receipt = try? JSONDecoder().decode(Receipt.self, from: data),
              let values = try? image.resourceValues(forKeys: [.fileSizeKey, .contentModificationDateKey, .isRegularFileKey]),
              values.isRegularFile == true,
              receipt.sha256 == descriptor.sha256, receipt.size == descriptor.size,
              Int64(values.fileSize ?? 0) == descriptor.size,
              values.contentModificationDate == receipt.modified else { return false }
        return true
    }

    /// A failed, cancelled or mismatched import never publishes the staging file.
    static func install(
        from source: URL, descriptor: TouchariumImageDescriptor, into directory: URL,
        progress: @Sendable (Double) -> Void = { _ in }
    ) throws -> URL {
        let access = source.startAccessingSecurityScopedResource()
        defer { if access { source.stopAccessingSecurityScopedResource() } }
        let values = try source.resourceValues(forKeys: [.fileSizeKey, .isRegularFileKey])
        guard source.pathExtension.lowercased() == "erofs", values.isRegularFile == true,
              Int64(values.fileSize ?? 0) == descriptor.size else {
            throw TouchariumImageError.unsupportedImage
        }
        let manager = FileManager.default
        try manager.createDirectory(at: directory, withIntermediateDirectories: true)
        let space = try manager.attributesOfFileSystem(forPath: directory.path)
        if let free = space[.systemFreeSize] as? NSNumber,
           free.int64Value < descriptor.size + (128 << 20) {
            throw TouchariumImageError.insufficientSpace
        }
        let staging = directory.appendingPathComponent(".toucharium-import-\(UUID().uuidString)")
        guard manager.createFile(atPath: staging.path, contents: nil) else {
            throw CocoaError(.fileWriteUnknown)
        }
        defer { try? manager.removeItem(at: staging) }
        let input = try FileHandle(forReadingFrom: source)
        defer { try? input.close() }
        let output = try FileHandle(forWritingTo: staging)
        defer { try? output.close() }
        var hasher = SHA256()
        var total: Int64 = 0
        while let block = try input.read(upToCount: 4 << 20), !block.isEmpty {
            try Task.checkCancellation()
            total += Int64(block.count)
            guard total <= descriptor.size else { throw TouchariumImageError.unsupportedImage }
            hasher.update(data: block)
            try output.write(contentsOf: block)
            progress(Double(total) / Double(descriptor.size))
        }
        let checksum = hasher.finalize().map { String(format: "%02x", $0) }.joined()
        guard total == descriptor.size, checksum == descriptor.sha256 else {
            throw TouchariumImageError.unsupportedImage
        }
        try Task.checkCancellation()
        try output.synchronize()
        try output.close()
        let destination = directory.appendingPathComponent(descriptor.filename)
        if manager.fileExists(atPath: destination.path) {
            let existing = try destination.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey])
            guard existing.isRegularFile == true, existing.isSymbolicLink != true else {
                throw TouchariumImageError.unsupportedImage
            }
            _ = try manager.replaceItemAt(destination, withItemAt: staging)
        } else {
            try manager.moveItem(at: staging, to: destination)
        }
        var image = destination
        var resource = URLResourceValues()
        resource.isExcludedFromBackup = true
        try image.setResourceValues(resource)
        let installed = try image.resourceValues(forKeys: [.contentModificationDateKey])
        guard let modified = installed.contentModificationDate else { throw CocoaError(.fileReadUnknown) }
        let receipt = Receipt(sha256: checksum, size: total, modified: modified)
        let url = receiptURL(in: directory)
        try manager.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try JSONEncoder().encode(receipt).write(to: url, options: .atomic)
        return destination
    }
}
