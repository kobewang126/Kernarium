// SPDX-License-Identifier: GPL-2.0-or-later

import XCTest

/// An opt-in probe of the already booted guest. Attachments show the actual
/// guest response; completing the tap alone is not an interaction verdict.
final class UbuntuTouchInteractionTests: XCTestCase {
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
                display.coordinate(withNormalizedOffset: CGVector(dx: x, dy: y)).tap()
                try await Task.sleep(for: .seconds(3))
            }
            let attachment = XCTAttachment(screenshot: app.screenshot())
            attachment.name = name
            attachment.lifetime = .keepAlways
            add(attachment)
        }
    }
}
