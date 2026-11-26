// SPDX-License-Identifier: GPL-2.0-or-later

import XCTest
import UIKit

/// Opt-in probes of host controls and the guest. Attachments show the actual
/// guest response; completing the tap alone is not an interaction verdict.
final class UbuntuTouchInteractionTests: XCTestCase {
    @MainActor
    func testPhoneLandscapeControls() throws {
        guard UIDevice.current.userInterfaceIdiom == .phone else {
            throw XCTSkip("requires an iPhone")
        }
        guard ProcessInfo.processInfo.environment["TOUCHARIUM_INTERACTION_PROBE"] == "1" else {
            throw XCTSkip("requires an imported image on an iPhone")
        }
        let app = XCUIApplication(bundleIdentifier:
            ProcessInfo.processInfo.environment["TOUCHARIUM_APP_ID"] ?? "org.toucharium.app")
        XCUIDevice.shared.orientation = .portrait
        app.launch()
        defer { XCUIDevice.shared.orientation = .portrait }
        let display = app.descendants(matching: .any)["framebufferView"]
        let settings = app.buttons["settingsButton"]
        XCTAssertTrue(settings.waitForExistence(timeout: 10))
        let portraitSettingsCenter = CGPoint(x: settings.frame.midX, y: settings.frame.midY)
        for orientation in [UIDeviceOrientation.landscapeLeft, .landscapeRight] {
            XCUIDevice.shared.orientation = orientation
            let moved = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
                display.exists && settings.exists && display.frame.width > display.frame.height
                    && settings.frame.minX >= display.frame.maxX
                    && display.frame.minY >= app.frame.minY + 24
                    && display.frame.maxY > app.frame.maxY - 40
            }, object: app)
            XCTAssertEqual(XCTWaiter.wait(for: [moved], timeout: 15), .completed)
            XCTAssertTrue(settings.isHittable)
            let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
            attachment.name = "phone-landscape-controls-\(orientation.rawValue)"
            attachment.lifetime = .keepAlways
            add(attachment)
        }
        XCUIDevice.shared.orientation = .portrait
        let restored = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            display.exists && display.frame.width < display.frame.height
        }, object: app)
        let result = XCTWaiter.wait(for: [restored], timeout: 15)
        // Simulator accessibility can temporarily omit the rotated control
        // subtree. Exercise its original portrait target and verify the sheet.
        app.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(
            dx: portraitSettingsCenter.x, dy: portraitSettingsCenter.y)).tap()
        XCTAssertTrue(app.buttons["settingsSaveButton"].waitForExistence(timeout: 10))
        app.buttons["Cancel"].tap()
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = "phone-portrait-restored"
        attachment.lifetime = .keepAlways
        add(attachment)
        XCTAssertEqual(result, .completed,
                       "display=\(display.exists ? String(describing: display.frame) : "missing"), "
                       + "settings=\(settings.exists ? String(describing: settings.frame) : "missing")")
    }

    @MainActor
    func testPadControlsRemainBelowGuest() async throws {
        guard UIDevice.current.userInterfaceIdiom == .pad else {
            throw XCTSkip("requires an iPad")
        }
        guard ProcessInfo.processInfo.environment["TOUCHARIUM_INTERACTION_PROBE"] == "1" else {
            throw XCTSkip("requires an imported image on an iPad")
        }
        let app = XCUIApplication(bundleIdentifier:
            ProcessInfo.processInfo.environment["TOUCHARIUM_APP_ID"] ?? "org.toucharium.app")
        if let forwarding = ProcessInfo.processInfo.environment["TOUCHARIUM_LAYOUT_HOST_FORWARD"] {
            app.launchEnvironment["KERNARIUM_HOST_FORWARD"] = forwarding
        }
        app.launch()
        defer { XCUIDevice.shared.orientation = .portrait }
        if let value = ProcessInfo.processInfo.environment["TOUCHARIUM_LAYOUT_GUEST_WARMUP_SECONDS"],
           let seconds = Double(value), seconds.isFinite, seconds > 0, seconds <= 180 {
            try await Task.sleep(for: .seconds(seconds))
        }
        let display = app.descendants(matching: .any)["framebufferView"]
        let settings = app.buttons["settingsButton"]
        for orientation in [UIDeviceOrientation.portrait, .landscapeLeft, .landscapeRight, .portrait] {
            XCUIDevice.shared.orientation = orientation
            let below = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
                display.exists && settings.exists && settings.frame.minY >= display.frame.maxY
            }, object: app)
            let result = XCTWaiter.wait(for: [below], timeout: 15)
            try await Task.sleep(for: .seconds(3))
            let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
            attachment.name = "pad-controls-\(orientation.rawValue)"
            attachment.lifetime = .keepAlways
            add(attachment)
            XCTAssertEqual(result, .completed,
                           "display=\(display.exists ? String(describing: display.frame) : "missing"), "
                           + "settings=\(settings.exists ? String(describing: settings.frame) : "missing")")
            XCTAssertTrue(settings.isHittable)
        }
    }

    @MainActor
    func testShellModeSelection() throws {
        guard ProcessInfo.processInfo.environment["TOUCHARIUM_INTERACTION_PROBE"] == "1" else {
            throw XCTSkip("requires an imported image")
        }
        let app = XCUIApplication(bundleIdentifier:
            ProcessInfo.processInfo.environment["TOUCHARIUM_APP_ID"] ?? "org.toucharium.app")
        app.activate()
        func picker() -> XCUIElement {
            app.buttons["settingsButton"].tap()
            let value = app.buttons["shellModePicker"]
            let form = app.collectionViews.firstMatch
            let header = app.navigationBars["Emulator settings"]
            XCTAssertTrue(form.waitForExistence(timeout: 5))
            for _ in 0..<10 {
                let visible = value.exists && value.isHittable
                    && value.frame.minY > header.frame.maxY + 8
                    && value.frame.maxY < form.frame.maxY - 16
                if visible { break }
                let down = value.exists && value.frame.minY <= header.frame.maxY + 8
                form.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: down ? 0.4 : 0.7))
                    .press(forDuration: 0.1, thenDragTo:
                        form.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: down ? 0.7 : 0.4)))
            }
            XCTAssertTrue(value.exists && value.isHittable)
            return value
        }
        func select(_ name: String, save: Bool) {
            picker().tap()
            let choice = app.buttons[name]
            XCTAssertTrue(choice.waitForExistence(timeout: 5), app.debugDescription)
            choice.tap()
            app.buttons[save ? "settingsSaveButton" : "Cancel"].tap()
        }
        select("Phone mode", save: true)
        select("Desktop windows", save: false)
        let unchanged = picker()
        XCTAssertTrue((unchanged.label + String(describing: unchanged.value)).contains("Phone mode"))
        app.buttons["Cancel"].tap()
        select("Desktop windows", save: true)
        let saved = picker()
        XCTAssertTrue((saved.label + String(describing: saved.value)).contains("Desktop windows"))
        app.buttons["Cancel"].tap()
    }
    @MainActor
    func testExternalImageImportPrompt() throws {
        guard ProcessInfo.processInfo.environment["TOUCHARIUM_EXTERNAL_IMAGE_TEST"] == "1" else {
            throw XCTSkip("requires a fresh external-image installation")
        }
        let app = XCUIApplication(bundleIdentifier:
            ProcessInfo.processInfo.environment["TOUCHARIUM_APP_ID"] ?? "org.toucharium.app")
        app.launch()
        XCTAssertTrue(app.buttons["importSystemImageButton"].waitForExistence(timeout: 15))
        XCTAssertFalse(app.descendants(matching: .any)["framebufferView"].exists)
        app.buttons["importSystemImageButton"].tap()
        XCTAssertTrue(app.buttons["Cancel"].waitForExistence(timeout: 10))
        app.buttons["Cancel"].tap()
        XCTAssertTrue(app.buttons["importSystemImageButton"].exists)
    }
    @MainActor
    func testSystemImageReplacementEntryAndCancellation() throws {
        guard ProcessInfo.processInfo.environment["TOUCHARIUM_IMAGE_CHANGE_TEST"] == "1" else {
            throw XCTSkip("requires an imported image on a dedicated simulator")
        }
        let app = XCUIApplication(bundleIdentifier:
            ProcessInfo.processInfo.environment["TOUCHARIUM_APP_ID"] ?? "org.toucharium.app")
        app.launchEnvironment["KERNARIUM_VCPU_COUNT"] = "4"
        app.launchEnvironment["KERNARIUM_GUEST_MEMORY_MIB"] = "2048"
        app.launch()
        XCTAssertTrue(app.buttons["settingsButton"].waitForExistence(timeout: 15))
        app.buttons["settingsButton"].tap()
        let change = app.buttons["changeSystemImageButton"]
        let form = app.collectionViews.firstMatch
        XCTAssertTrue(form.waitForExistence(timeout: 5))
        for _ in 0..<8 {
            if change.exists && change.isHittable { break }
            form.swipeUp()
        }
        XCTAssertTrue(change.isHittable)
        change.tap()
        XCTAssertTrue(app.alerts.firstMatch.waitForExistence(timeout: 5))
        app.alerts.buttons["Cancel"].tap()
        XCTAssertTrue(app.buttons["settingsSaveButton"].exists)
        change.tap()
        app.alerts.firstMatch.buttons["Stop and continue"].firstMatch.tap()
        let importButton = app.buttons["importSystemImageButton"]
        XCTAssertTrue(importButton.waitForExistence(timeout: 60))
        XCTAssertTrue(importButton.isEnabled)
        XCTAssertFalse(app.descendants(matching: .any)["framebufferView"].exists)
        let policy = app.buttons["imageDataPolicyPicker"]
        XCTAssertTrue(policy.exists)
        XCTAssertTrue((policy.label + String(describing: policy.value)).contains("Keep existing data"))
        policy.tap()
        app.buttons["Start fresh"].firstMatch.tap()
        policy.tap()
        app.buttons["Keep existing data"].firstMatch.tap()
        importButton.tap()
        XCTAssertTrue(app.buttons["Cancel"].waitForExistence(timeout: 10))
        app.buttons["Cancel"].tap()
        app.buttons["keepCurrentImageButton"].tap()
        XCTAssertTrue(app.staticTexts["Reopen Toucharium"].waitForExistence(timeout: 5))
        app.terminate()
        app.launch()
        XCTAssertTrue(app.buttons["settingsButton"].waitForExistence(timeout: 15))
        XCTAssertFalse(app.buttons["importSystemImageButton"].exists)
    }

    @MainActor
    private func selectKeyboard(_ name: String, in app: XCUIApplication, save: Bool = true) {
        app.buttons["settingsButton"].tap()
        let source = app.buttons["keyboardSourcePicker"]
        XCTAssertTrue(source.waitForExistence(timeout: 5))
        for _ in 0..<4 {
            if source.isHittable { break }
            app.swipeUp()
        }
        source.tap()
        let choice = app.buttons[name]
        XCTAssertTrue(choice.waitForExistence(timeout: 5))
        choice.tap()
        if save { app.buttons["settingsSaveButton"].tap() }
        else { app.buttons["Cancel"].tap() }
    }

    @MainActor
    func testKeyboardSourceSelection() async throws {
        let environment = ProcessInfo.processInfo.environment
        guard environment["TOUCHARIUM_INTERACTION_PROBE"] == "1" else {
            throw XCTSkip("requires the Toucharium keyboard-source controls")
        }
        let app = XCUIApplication(bundleIdentifier:
            environment["TOUCHARIUM_APP_ID"] ?? "org.toucharium.app")
        app.activate()
        XCTAssertTrue(app.buttons["settingsButton"].waitForExistence(timeout: 15))
        let initiallyEnabled = app.buttons["keyboardButton"].isEnabled
        selectKeyboard(initiallyEnabled ? "Ubuntu Touch keyboard" : "iPhone keyboard",
                       in: app, save: false)
        XCTAssertEqual(app.buttons["keyboardButton"].isEnabled, initiallyEnabled)
        let names = initiallyEnabled
            ? ["Ubuntu Touch keyboard", "iPhone keyboard"]
            : ["iPhone keyboard", "Ubuntu Touch keyboard"]
        for name in names {
            selectKeyboard(name, in: app)
            XCTAssertEqual(app.buttons["keyboardButton"].isEnabled,
                           name == "iPhone keyboard")
        }
    }

    @MainActor
    func testDismissHostKeyboard() async throws {
        let environment = ProcessInfo.processInfo.environment
        guard environment["TOUCHARIUM_INTERACTION_PROBE"] == "1" else {
            throw XCTSkip("requires an already booted Ubuntu Touch guest")
        }
        let app = XCUIApplication(bundleIdentifier:
            environment["TOUCHARIUM_APP_ID"] ?? "org.toucharium.app")
        app.activate()
        let keyboard = app.buttons["keyboardButton"]
        XCTAssertTrue(keyboard.waitForExistence(timeout: 15))
        if !keyboard.isEnabled {
            selectKeyboard("iPhone keyboard", in: app)
        }
        if keyboard.label == "Hide keyboard" { keyboard.tap() }
        keyboard.tap()
        let shown = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "label == %@", "Hide keyboard"),
            object: keyboard)
        XCTAssertEqual(XCTWaiter.wait(for: [shown], timeout: 5), .completed)
        XCTAssertTrue(app.keyboards.firstMatch.waitForExistence(timeout: 5))
        let display = app.descendants(matching: .any)["framebufferView"]
        XCTAssertTrue(display.waitForExistence(timeout: 5))
        display.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.15)).tap()
        let hidden = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "label == %@", "Show keyboard"),
            object: keyboard)
        XCTAssertEqual(XCTWaiter.wait(for: [hidden], timeout: 5), .completed)
        XCTAssertTrue(app.keyboards.allElementsBoundByIndex.isEmpty)
    }

    @MainActor
    func testGuestConsoleCommand() async throws {
        guard let encoded = ProcessInfo.processInfo.environment[
            "TOUCHARIUM_CONSOLE_COMMAND"
        ], let bytes = Data(base64Encoded: encoded),
           let command = String(data: bytes, encoding: .utf8),
           command.utf8.count <= 8192 else {
            throw XCTSkip("requires a bounded guest console command")
        }
        let app = XCUIApplication(bundleIdentifier:
            ProcessInfo.processInfo.environment["TOUCHARIUM_APP_ID"] ?? "org.toucharium.app")
        app.activate()
        if let wakeKey = ProcessInfo.processInfo.environment["TOUCHARIUM_WAKE_KEY"] {
            guard ["guestPowerButton", "guestVolumeUpButton"].contains(wakeKey) else {
                XCTFail("unsupported wake key")
                return
            }
            let keys = app.buttons["specialKeysButton"]
            if keys.exists && keys.label == "Show special keys" { keys.tap() }
            let key = app.buttons[wakeKey]
            XCTAssertTrue(key.waitForExistence(timeout: 5))
            key.tap()
            if keys.exists { keys.tap() }
            try await Task.sleep(for: .seconds(2))
        }
        let toggle = app.buttons["displayModeButton"]
        XCTAssertTrue(toggle.waitForExistence(timeout: 15))
        if toggle.label == "Show serial console" { toggle.tap() }
        let console = app.descendants(matching: .any)["serialConsoleView"]
        XCTAssertTrue(console.waitForExistence(timeout: 5))
        console.tap()
        let keyboard = app.buttons["keyboardButton"]
        if keyboard.label == "Show keyboard" { keyboard.tap() }
        let focused = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "label == %@", "Hide keyboard"),
            object: keyboard
        )
        guard XCTWaiter.wait(for: [focused], timeout: 5) == .completed else {
            XCTFail("serial console did not acquire keyboard focus")
            return
        }
        app.typeText(command)
        try await Task.sleep(for: .seconds(2))
        if keyboard.label == "Hide keyboard" { keyboard.tap() }
        if toggle.label == "Show framebuffer" { toggle.tap() }
        XCTAssertTrue(NSPredicate(format: "label == %@", "Show serial console")
            .evaluate(with: toggle))
        if ProcessInfo.processInfo.environment["TOUCHARIUM_TAP_AFTER_CONSOLE"] == "1" {
            let display = app.descendants(matching: .any)["framebufferView"]
            display.coordinate(withNormalizedOffset: CGVector(dx: 0.85, dy: 0.96)).tap()
            try await Task.sleep(for: .seconds(3))
        }
        if ProcessInfo.processInfo.environment["TOUCHARIUM_SWIPE_RIGHT_EDGE"] == "1" {
            let display = app.descendants(matching: .any)["framebufferView"]
            display.coordinate(withNormalizedOffset: CGVector(dx: 0.995, dy: 0.25))
                .press(forDuration: 0.1, thenDragTo: display.coordinate(
                    withNormalizedOffset: CGVector(dx: 0.25, dy: 0.25)))
            try await Task.sleep(for: .seconds(3))
        }
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = "guest-after-console"
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    @MainActor
    func testTapGuestDisplay() async throws {
        let environment = ProcessInfo.processInfo.environment
        guard environment["TOUCHARIUM_INTERACTION_PROBE"] == "1" else {
            throw XCTSkip("requires an already booted Ubuntu Touch guest")
        }
        let x = Double(environment["TOUCHARIUM_TAP_X"] ?? "0.85") ?? -1
        let y = Double(environment["TOUCHARIUM_TAP_Y"] ?? "0.96") ?? -1
        XCTAssertTrue((0...1).contains(x) && (0...1).contains(y))
        guard (0...1).contains(x), (0...1).contains(y) else { return }
        let app = XCUIApplication(bundleIdentifier:
            environment["TOUCHARIUM_APP_ID"] ?? "org.toucharium.app")
        app.activate()
        let toggle = app.buttons["displayModeButton"]
        if toggle.waitForExistence(timeout: 5) && toggle.label == "Show framebuffer" {
            toggle.tap()
        }
        let display = app.descendants(matching: .any)["framebufferView"]
        XCTAssertTrue(display.waitForExistence(timeout: 15))
        if environment["TOUCHARIUM_SWIPE_RIGHT_EDGE"] == "1" {
            display.coordinate(withNormalizedOffset: CGVector(dx: 0.995, dy: 0.25))
                .press(forDuration: 0.1, thenDragTo: display.coordinate(
                    withNormalizedOffset: CGVector(dx: 0.25, dy: 0.25)))
            try await Task.sleep(for: .seconds(2))
        }
        for name in ["before-touch", "after-touch"] {
            if name == "after-touch" {
                let target = environment["TOUCHARIUM_SCREEN_TAP"] == "1" ? app : display
                target.coordinate(withNormalizedOffset: CGVector(dx: x, dy: y)).tap()
                try await Task.sleep(for: .seconds(3))
            }
            let attachment = XCTAttachment(screenshot: app.screenshot())
            attachment.name = name
            attachment.lifetime = .keepAlways
            add(attachment)
        }
    }
}
