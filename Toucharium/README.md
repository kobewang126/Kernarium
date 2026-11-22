# Toucharium

Toucharium is an iOS host for the official UBports Ubuntu Touch arm64 PDK
userspace. Its independent application target shares Kernarium's Linux runtime,
GuestHost display and input, and guest settings. It runs on an Apple silicon
Mac in Designed for iPad mode. Runtime validation uses the iPhone 17 Simulator.
Lomiri startup and interaction remain under validation. Host controls sit below
the guest display in one row so Ubuntu Touch retains its full edges for gestures.
The host keyboard is toggled from the controls; touching the guest display
dismisses it while forwarding the contact to Ubuntu Touch.
Ubuntu's grid-unit and web-content density follow the guest's boot display
density, so Retina increases detail while preserving the interface's size in
host points. Display-density changes take effect on the next application launch.
Retina and automatic display resizing are enabled by the display-policy migration;
subsequent choices in Settings are preserved.
Emulator Settings selects the iPhone or Ubuntu Touch on-screen keyboard
for the next application launch; Save applies the selection and Cancel discards
it. Ubuntu mode leaves text focus and dismissal
to Lomiri; iPhone mode suppresses the guest keyboard.
The experimental Ubuntu keyboard can submit a black surface on the Simulator;
iPhone keyboard mode is the default.

The application uses the original Toucharium mark in
`Branding/Toucharium.svg`. From the repository root,
`swift Toucharium/scripts/render-icon.swift` renders its opaque App Store icon.

## Source and licensing

Toucharium extends Kernarium and uses the official UBports userspace. Host code
and first-party image tooling follow the repository's GPL-2.0-or-later licence.
The Lomiri QML override retains GPL-3.0-only; guest packages retain their own
licences. See [the licensing guide](../LICENSES/README.md).

The source tree carries the application, kernel configuration and patch series,
and image-policy producers. Base images and packaged applications are separate
binary artifacts. Distributing them also requires the applicable notices and
corresponding source for the exact versions they contain; the image producer
and its input digests alone do not supply all guest package sources.

The application selects the image produced by
[`tools/rootfs/ubuntu-touch`](../tools/rootfs/ubuntu-touch/README.md) on first
launch. An optional bundled image is used directly from the read-only application bundle
on a fresh install and replaces selections of the legacy staged PDK images;
it is not copied into Documents. Otherwise put the image in Documents.
Custom image selections are preserved. The generic Linux runtime starts the image's own systemd and
LightDM session; it does not boot an Android ramdisk.
Base images are attached as read-only host files, including inside a signed
iOS application bundle; all guest writes go to the separate overlay.

## Build and run

Build the verified dependencies, compatible Linux kernel artifact and accepted
boot base before the Linux runtime. The owning build and packaging contracts
are in [`Kernarium`](../Kernarium/README.md) and
[`dependencies`](../dependencies/README.md). Package the complete runtime set
with `Kernarium/scripts/package-ios-frameworks.sh`, then build the `Toucharium`
scheme in `Toucharium.xcodeproj`. Signing uses the shared ignored
`GuestHost/Config/Signing.local.xcconfig`.

Build for the iPhone 17 Simulator with:

```sh
xcodebuild build \
  -project Toucharium/Toucharium.xcodeproj -scheme Toucharium \
  -destination 'platform=iOS Simulator,name=iPhone 17'
```

Set `TOUCHARIUM_BUNDLED_IMAGE` to the complete pinned PDK 470 r1 EROFS
image when building an all-in-one application. Without it, stage an image in
the application's Documents directory before launching. The opt-in interaction probes under `UITests` operate on
the already booted guest. Their screenshots and guest response determine whether
an interaction works; completing a synthetic tap alone does not prove it.

The command-line team setting also signs the Swift Package resource bundle.

Simulator builds use the separately packaged software-rendering slices;
Designed for iPad uses the device slices and their Metal graphics stack.
Ubuntu Touch keeps its writable overlay in Documents/UbuntuTouch. Cover
installations preserve it. The application selects AppArmor and includes a
boot-policy archive that applies its portrait phone layout, touchscreen mapping
and application software OpenGL configuration before systemd starts. The desktop
keeps its existing renderer. Application updates replace this policy without
replacing the rootfs or requiring an SSH session.

The Xcode build stages this archive through `scripts/stage-guest-policy.sh`.
Small display-policy archives override its layout for the actual boot density;
the application combines the selected override with its keyboard policy.
The display producer requires the original Lomiri Shell QML from the pinned
rootfs and verifies its digest before generating shell overrides.
It requires the pinned Qt Wayland Debian package, the CMake-built
`uml-initramfs` host tool and zstd. The owning producer and package pin are in
[`tools/rootfs/ubuntu-touch`](../tools/rootfs/ubuntu-touch/README.md).

For a local Mac test, the hosted harness can import the pinned image from a
loopback HTTP server with `TEST_RUNNER_TOUCHARIUM_IMAGE_URL` set to its URL.
It checks the image digest before publishing it in Documents, then ends the
import run. Relaunch without that variable to boot. This avoids granting the
application access to the source checkout or writing into its protected
container from another process.
