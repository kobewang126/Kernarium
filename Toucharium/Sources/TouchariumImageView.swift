// SPDX-License-Identifier: GPL-2.0-or-later

import Combine
import SwiftUI
import UniformTypeIdentifiers

@MainActor
final class TouchariumImageStore: ObservableObject {
    @Published private(set) var ready = false
    @Published private(set) var progress: Double?
    @Published var error: String?
    let descriptor: TouchariumImageDescriptor?
    private let directory: URL
    private var operation: Task<URL, Error>?
    private var importID: UUID?

    init(directory: URL = RootfsImage.documentsDirectory) {
        self.directory = directory
        do {
            try TouchariumImage.removeInterruptedImports(in: directory)
            let descriptor = try TouchariumImageDescriptor.load()
            self.descriptor = descriptor
            ready = TouchariumImage.isInstalled(descriptor, in: directory)
        } catch {
            descriptor = nil
            self.error = error.localizedDescription
        }
    }

    func importImage(_ url: URL) {
        guard operation == nil, let descriptor else { return }
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
            Text("Toucharium runs a separate Ubuntu Touch system image. Import the supported image to get started.")
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
                    .disabled(store.descriptor == nil)
                    .accessibilityIdentifier("importSystemImageButton")
            }
            if let error = store.error {
                Text(error).foregroundStyle(.red).multilineTextAlignment(.center)
                    .accessibilityIdentifier("imageImportError")
            }
            Text("Your existing Ubuntu Touch data is kept when you import a system image.")
                .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
        }
        .padding(32)
        .frame(maxWidth: 540)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .fileImporter(isPresented: $choosingFile, allowedContentTypes: [.item]) { result in
            switch result {
            case let .success(url): store.importImage(url)
            case let .failure(error): store.error = error.localizedDescription
            }
        }
    }
}
