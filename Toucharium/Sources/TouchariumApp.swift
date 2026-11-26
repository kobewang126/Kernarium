// SPDX-License-Identifier: GPL-2.0-or-later

import SwiftUI

@main
struct TouchariumApp: App {
    init() {
        let documents = FileManager.default.urls(
            for: .documentDirectory, in: .userDomainMask
        )[0]
        // Resolve the verified import destination before the launcher snapshots settings.
        let preferences = UserDefaults.standard
        preferences.register(defaults: [
            "toucharium.shellMode": UIDevice.current.userInterfaceIdiom == .pad ? "desktop" : "phone"
        ])
        if preferences.integer(forKey: "toucharium.phoneDisplayPolicyVersion") < 2 {
            preferences.set(true, forKey: "emulator.retinaMode")
            preferences.set(true, forKey: "emulator.autoResizeGuest")
            preferences.set(2, forKey: "toucharium.phoneDisplayPolicyVersion")
        }
        let installed = TouchariumImage.installation(in: documents,
            legacyFilename: preferences.string(forKey: "emulator.rootfsFilename"))
        preferences.set(installed?.filename ?? TouchariumImage.installedFilename,
                        forKey: "emulator.rootfsFilename")
        // Before any view: the display and the terminal compile Metal
        // pipelines as they are created, and that reads the shader cache.
        MetalShaderCache.removeIfBloatedBeforeFirstUse()
        // Mesa would otherwise keep a disk cache of its own below
        // $HOME/.cache, which a device container does not let it create.
        // Give it a bounded home in the application's cache directory, here
        // and on a Mac alike.
        MesaShaderCache.configureBeforeFirstUse()
        // The host GL provider selects its driver through the environment
        // when it creates its display, on a runtime thread during boot. The
        // terminal's libghostty copied the environment at its first
        // initialization, so a variable added after that leaves its copy
        // pointing at freed memory and the next terminal configuration
        // crashes. Every process variable is set here, before any view.
        // The Simulator has no Metal 4 device, so its provider is Mesa's
        // llvmpipe rasterizer, which Mesa selects when software rendering
        // is forced.
        #if targetEnvironment(simulator)
        setenv("LIBGL_ALWAYS_SOFTWARE", "true", 1)
        #else
        setenv("MESA_LOADER_DRIVER_OVERRIDE", "zink", 1)
        #endif
        // The singleton snapshots preferences and queries the runtime.
        // Initialize it only after selecting the image and host GL driver.
        EmulatorLauncher.shared.persistentOverlayDirectory = documents
            .appendingPathComponent(installed?.dataDirectory ?? "UbuntuTouch", isDirectory: true)
        EmulatorLauncher.shared.linuxAppArmor = true
        let prefix = preferences.string(forKey: "toucharium.shellMode") == "desktop"
            ? "TouchariumDesktop" : "Toucharium"
        let policyName = prefix + ((preferences.string(forKey: "toucharium.keyboardSource") ?? "ubuntu") == "ubuntu"
            ? "UbuntuKeyboardPolicy" : "GuestPolicy")
        guard let policy = Bundle.main.url(
            forResource: policyName, withExtension: "cpio"
        ) else {
            fatalError("Toucharium guest policy is missing from the application")
        }
        EmulatorLauncher.shared.linuxBootPolicy = policy
        EmulatorLauncher.shared.linuxBootPolicyForDisplay = { dotsPerInch in
            // The host uses 160 DPI per pixel-to-point factor; Lomiri uses
            // eight pixels per grid unit at that baseline. Read the actual
            // boot geometry so Retina and fractional native scales agree.
            let gridUnit = min(64, max(8, Int((Double(dotsPerInch) / 20).rounded())))
            guard let displayPolicy = Bundle.main.url(
                forResource: "\(prefix)Display\(gridUnit)", withExtension: "cpio"
            ) else {
                throw CocoaError(.fileNoSuchFile)
            }
            var archive = try Data(contentsOf: policy)
            archive.append(try Data(contentsOf: displayPolicy))
            let combined = FileManager.default.temporaryDirectory
                .appendingPathComponent("TouchariumBootPolicy.cpio")
            try archive.write(to: combined, options: .atomic)
            print("Toucharium: display policy \(dotsPerInch) DPI, grid unit \(gridUnit)")
            return combined
        }
    }

    var body: some Scene {
        WindowGroup {
            TouchariumRootView()
        }
    }
}

private struct TouchariumRootView: View {
    @AppStorage("toucharium.keyboardSource") private var keyboardSource = "ubuntu"
    @AppStorage("toucharium.shellMode") private var shellMode = "phone"
    @StateObject private var image = TouchariumImageStore()

    var body: some View {
        if image.needsRelaunch {
            ContentUnavailableView("Reopen Toucharium", systemImage: "arrow.clockwise",
                description: Text("Close Toucharium from the app switcher, then open it again to start the selected system image."))
                .accessibilityIdentifier("imageChangeRelaunchNotice")
        } else if image.ready && !image.replacing {
            ContentView(controlsBelowGuest: true, keyboardSource: $keyboardSource,
                        supportedRootfsNames: [image.filename], shellMode: $shellMode,
                        changeSystemImage: {
                Task {
                    await image.beginReplacement {
                        let launcher = EmulatorLauncher.shared
                        launcher.stop()
                        let clock = ContinuousClock()
                        let deadline = clock.now.advanced(by: .seconds(45))
                        while launcher.phase == .running && clock.now < deadline {
                            do { try await Task.sleep(for: .milliseconds(200)) }
                            catch { return false }
                        }
                        return launcher.phase != .running
                    }
                }
            })
        } else {
            TouchariumImageView(store: image)
        }
    }
}
