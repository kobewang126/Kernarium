// SPDX-License-Identifier: GPL-2.0-or-later

import Combine
import SwiftUI
import UniformTypeIdentifiers

@MainActor
final class TouchariumImageStore: ObservableObject {
    @Published private(set) var ready = false
    @Published private(set) var progress: Double?
    @Published var error: String?
    @Published private(set) var descriptor: TouchariumImageDescriptor?
    private(set) var filename = TouchariumImage.installedFilename
    private let directory: URL
    private var operation: Task<URL, Error>?
    private var importID: UUID?

    init(directory: URL = RootfsImage.documentsDirectory) {
        self.directory = directory
        do {
            try TouchariumImage.removeInterruptedImports(in: directory)
            if let installed = TouchariumImage.installation(in: directory,
                legacyFilename: UserDefaults.standard.string(forKey: "emulator.rootfsFilename")) {
                descriptor = installed.descriptor
                filename = installed.filename
                ready = true
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    func importImages(_ urls: [URL]) {
        guard operation == nil else { return }
        let images = urls.filter { $0.pathExtension.lowercased() == "erofs" }
        let descriptions = urls.filter { $0.lastPathComponent.lowercased().hasSuffix(".import.json") }
        guard urls.count == 2, let url = images.first, images.count == 1,
              let description = descriptions.first, descriptions.count == 1 else {
            error = TouchariumImageError.invalidSelection.localizedDescription
            return
        }
        let descriptor: TouchariumImageDescriptor
        do {
            descriptor = try TouchariumImageDescriptor.load(from: description)
        } catch {
            self.error = error.localizedDescription
            return
        }
        error = nil
        progress = 0
        let identifier = UUID()
        importID = identifier
        let directory = directory
        let task = Task.detached(priority: .userInitiated) { [weak self] in
            try TouchariumImage.install(from: url, descriptor: descriptor, into: directory) { value in
                Task { @MainActor [weak self] in
                    guard self?.importID == identifier else { return }
                    self?.progress = value
                }
            }
        }
        operation = task
        Task {
            do {
                _ = try await task.value
                self.descriptor = descriptor
                filename = TouchariumImage.installedFilename
                ready = true
            } catch is CancellationError {
                error = nil
            } catch {
                self.error = error.localizedDescription
            }
            operation = nil
            importID = nil
            progress = nil
        }
    }

    func cancel() { operation?.cancel() }
}

struct TouchariumImageView: View {
    @ObservedObject var store: TouchariumImageStore
    @State private var choosingFile = false

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "externaldrive.badge.plus")
                .font(.system(size: 56))
                .foregroundStyle(.tint)
            Text("Choose your system image")
                .font(.title2.bold())
            Text("Select a system image (.erofs) and its matching import file (.import.json) together.")
                .multilineTextAlignment(.center)
            if let descriptor = store.descriptor {
                Text(descriptor.filename).font(.footnote).foregroundStyle(.secondary)
            }
            if let progress = store.progress {
                ProgressView("Importing and verifying…", value: progress)
                    .accessibilityIdentifier("imageImportProgress")
                Button("Cancel import") { store.cancel() }
            } else {
                Button("Import system image") { choosingFile = true }
                    .buttonStyle(.borderedProminent)
                    .accessibilityIdentifier("importSystemImageButton")
            }
            if let error = store.error {
                Text(error).foregroundStyle(.red).multilineTextAlignment(.center)
                    .accessibilityIdentifier("imageImportError")
            }
            Text("Your existing Ubuntu Touch data is kept when you import a system image.")
                .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
            Text("File verification checks integrity, not the source or endorsement of an image.")
                .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
        }
        .padding(32)
        .frame(maxWidth: 540)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .fileImporter(isPresented: $choosingFile, allowedContentTypes: [.item], allowsMultipleSelection: true) { result in
            switch result {
            case let .success(urls): store.importImages(urls)
            case let .failure(error): store.error = error.localizedDescription
            }
        }
    }
}
