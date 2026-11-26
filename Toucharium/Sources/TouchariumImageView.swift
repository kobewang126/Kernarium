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
    @Published private(set) var replacing = false
    @Published private(set) var stopping = false
    @Published private(set) var stopFailed = false
    @Published private(set) var needsRelaunch = false
    @Published var preserveSystemData = true
    private(set) var filename = TouchariumImage.installedFilename
    private let directory: URL
    private let defaults: UserDefaults
    private static let replacementKey = "toucharium.imageReplacementRequested"
    private var operation: Task<URL, Error>?
    private var importID: UUID?

    init(directory: URL = RootfsImage.documentsDirectory, defaults: UserDefaults = .standard) {
        self.directory = directory
        self.defaults = defaults
        do {
            try TouchariumImage.removeInterruptedImports(in: directory)
            if let installed = TouchariumImage.installation(in: directory,
                legacyFilename: defaults.string(forKey: "emulator.rootfsFilename")) {
                descriptor = installed.descriptor
                filename = installed.filename
                ready = true
                replacing = defaults.bool(forKey: Self.replacementKey)
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    func beginReplacement(stop: @MainActor () async -> Bool) async {
        guard operation == nil, !replacing, ready else { return }
        defaults.set(true, forKey: Self.replacementKey)
        error = nil
        stopping = true
        replacing = true
        stopFailed = !(await stop())
        stopping = false
        if stopFailed {
            error = "The system has not stopped yet. Close and reopen Toucharium to continue changing the image."
        }
    }

    func keepCurrentImage() {
        guard operation == nil, !stopping else { return }
        defaults.removeObject(forKey: Self.replacementKey)
        replacing = false
        needsRelaunch = true
    }

    func importImages(_ urls: [URL]) {
        guard operation == nil, !stopping, !stopFailed else { return }
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
        let previousFilename = ready ? filename : nil
        let preserveData = preserveSystemData
        let task = Task.detached(priority: .userInitiated) { [weak self] in
            try TouchariumImage.install(from: url, descriptor: descriptor, into: directory,
                                        previousFilename: previousFilename, preserveData: preserveData) { value in
                Task { @MainActor [weak self] in
                    guard self?.importID == identifier else { return }
                    self?.progress = value
                }
            }
        }
        operation = task
        Task {
            do {
                let destination = try await task.value
                self.descriptor = descriptor
                filename = destination.lastPathComponent
                ready = true
                if replacing {
                    defaults.removeObject(forKey: Self.replacementKey)
                    needsRelaunch = true
                    replacing = false
                }
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
    @State private var confirmingDataReset = false

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "externaldrive.badge.plus")
                .font(.system(size: 56))
                .foregroundStyle(.tint)
            Text(store.replacing ? "Change your system image" : "Choose your system image")
                .font(.title2.bold())
            Text("Select a system image (.erofs) and its matching import file (.import.json) together.")
                .multilineTextAlignment(.center)
            if store.replacing {
                Picker("System data", selection: $store.preserveSystemData) {
                    Text("Keep existing data").tag(true)
                    Text("Start fresh").tag(false)
                }
                .pickerStyle(.menu)
                .disabled(store.stopping || store.stopFailed || store.progress != nil)
                .accessibilityIdentifier("imageDataPolicyPicker")
            }
            if store.stopping {
                ProgressView("Stopping system…")
                    .accessibilityIdentifier("imageChangeStoppingProgress")
            } else if let progress = store.progress {
                ProgressView("Importing and verifying…", value: progress)
                    .accessibilityIdentifier("imageImportProgress")
                Button("Cancel import") { store.cancel() }
            } else {
                Button("Import system image") {
                    if store.preserveSystemData { choosingFile = true }
                    else { confirmingDataReset = true }
                }
                    .buttonStyle(.borderedProminent)
                    .disabled(store.stopFailed)
                    .accessibilityIdentifier("importSystemImageButton")
                if store.replacing {
                    Button("Keep current image") { store.keepCurrentImage() }
                        .accessibilityIdentifier("keepCurrentImageButton")
                }
            }
            if let error = store.error {
                Text(error).foregroundStyle(.red).multilineTextAlignment(.center)
                    .accessibilityIdentifier("imageImportError")
            }
            Text(store.preserveSystemData
                ? "Your existing system data is kept. Choose a compatible system image."
                : "Existing system data will be deleted after the new image is verified and selected.")
                .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
            Text("File verification checks integrity, not the source or endorsement of an image.")
                .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
        }
        .padding(32)
        .frame(maxWidth: 540)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .alert("Clear existing system data?", isPresented: $confirmingDataReset) {
            Button("Cancel", role: .cancel) {}
            Button("Choose new image", role: .destructive) { choosingFile = true }
        } message: {
            Text("Your existing data is deleted only after the new image is imported successfully. Cancelling or a failed verification keeps the current data.")
        }
        .fileImporter(isPresented: $choosingFile, allowedContentTypes: [.item], allowsMultipleSelection: true) { result in
            switch result {
            case let .success(urls): store.importImages(urls)
            case let .failure(error): store.error = error.localizedDescription
            }
        }
    }
}
