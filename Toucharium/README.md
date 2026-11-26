# Toucharium

Toucharium is an iOS host for the official UBports Ubuntu Touch arm64 PDK
userspace. Its independent application target shares Kernarium's Linux runtime,
GuestHost display and input, and guest settings. It runs on an Apple silicon
Mac in Designed for iPad mode. Runtime validation uses iPhone and iPad simulators.
Lomiri startup and interaction remain under validation. Host controls sit below
the guest display in one row on iPad and portrait iPhone. Landscape iPhone
places them in a right-hand column and reserves space above the guest for its
pull-down panel; the bottom retains only the system safe area.
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
Ubuntu Touch keyboard mode is the default when no keyboard preference has been saved.
Existing selections are preserved. Emulator Settings also selects Phone mode
or Desktop windows; the latter gives Ubuntu applications window title bars
and controls. iPad defaults to Desktop windows and iPhone defaults to Phone
mode; existing selections are preserved. Save applies the choice on the next
application launch, and Cancel preserves the previous choice. Desktop mode selects a desktop device profile
without the phone portrait constraint and retains the selected mode on
touch-only devices. Both modes use the same external image.

The application uses the original Toucharium mark in
`Branding/Toucharium.svg`. From the repository root,
`swift Toucharium/scripts/render-icon.swift` renders its opaque App Store icon.
The application privacy manifest declares local settings, file metadata,
storage capacity and elapsed-time access; it declares no tracking or collected
data. Check built application and framework manifests with
`python3 scripts/check-privacy-manifests.py <application.app>`.

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

The application imports the versioned image produced by
[`tools/rootfs/ubuntu-touch`](../tools/rootfs/ubuntu-touch/README.md).
The application bundle contains no root filesystem. On first launch a file
picker imports a user-selected EROFS image and matching `.import.json` descriptor
from the packaging tool. It checks the supported policy version and image format,
verifies the complete size and SHA-256, and publishes the image in Documents
only after verification. No bundled digest pins imports to a particular build.
This check establishes file integrity, not image provenance or endorsement.
Cancellation or a checksum mismatch discards the staging file. The installed
image is excluded from device backups; the writable guest
data remains in Documents and survives application updates.
Existing verified installations remain usable after upgrading.
Emulator Settings can change the system image. It stops the guest before import.
Keeping the writable data is the default and requires a compatible replacement
image. Start fresh selects an empty data environment and deletes the previous
data only after the new image is published. A persisted deletion marker lets
startup finish interrupted cleanup before the new guest runs; no data backup
is retained.
A replacement is published through an atomic installation receipt only after
verification; a failed or cancelled import leaves the previous image selected.
The application must be closed and reopened after changing the image or keeping
the previous one, because each process runs one guest. An interrupted change can
be continued at the next launch before a guest starts.
Images whose installation receipt no longer matches their file metadata must
be imported and verified again. CPU, display and keyboard preferences are preserved.
The generic Linux runtime starts the image's own systemd and LightDM session;
it does not boot an Android ramdisk. The base is read-only and guest writes
use the separate overlay.

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

The image producer generates the external import descriptor alongside the image.
Neither file is bundled with the application. `TOUCHARIUM_BUNDLED_IMAGE` is rejected.
The opt-in interaction probes under `UITests` operate on the already booted
guest. Screenshots and guest response determine whether an interaction works;
completing a synthetic tap alone does not prove it.

The command-line team setting also signs the Swift Package resource bundle.

Simulator builds use the separately packaged software-rendering slices;
Designed for iPad uses the device slices and their Metal graphics stack.
The installation receipt selects the writable overlay directory in Documents.
Cover installations preserve it. The image carries the portrait phone policy, input
mapping, locale initialization, native Mir GPU compatibility library and
application access policy. The application supplies the keyboard and interface selections,
display-density override and a small migration bootstrap through CPIO.
Before systemd starts, the bootstrap runs the immutable image's migration
implementation. It validates the managed file manifest, replaces only known
previous policy contents, keeps a backup of replaced files, and preserves
unknown customizations and user data. Completed migrations are idempotent.
Changing systemd policy therefore takes effect before units are loaded.

The Xcode build stages the dynamic archives through
`scripts/stage-guest-policy.sh`. The display producer verifies the original
pinned Lomiri Shell and OrientedShell before generating density and mode overrides. It uses the
CMake-built `uml-initramfs` host tool. Image policy ownership, receipts and
migration contracts are in
[`tools/rootfs/ubuntu-touch`](../tools/rootfs/ubuntu-touch/README.md).

For a local Mac test, the hosted harness can import an image from a
loopback HTTP server with `TEST_RUNNER_TOUCHARIUM_IMAGE_URL` set to its URL
and `TEST_RUNNER_TOUCHARIUM_IMAGE_DESCRIPTOR_URL` set to the descriptor URL.
It checks the image digest before publishing it in Documents, then ends the
import run. Relaunch without that variable to boot. This avoids granting the
application access to the source checkout or writing into its protected
container from another process.

## Store builds

The scheme archives the universal iPhone and iPad `AppStore` configuration. Mac distribution
as Designed for iPhone or iPad is disabled for that configuration. It uses the store loader and
runtime without JIT, console input, display mirroring or automation overrides;
Picture in Picture is unavailable and the serial console is read-only in that
configuration. Ordinary Debug and
Release builds retain their development features.

Build both `kernarium-ios-device-app-store` and
`kernarium-ios-device-android-app-store`, then package with
`KERNARIUM_XCFRAMEWORK_OUTPUT=.build/toucharium-app-store-xcframeworks Kernarium/scripts/package-ios-frameworks.sh --app-store`.
The store frameworks have their own directory so development builds retain
their runtime slices.

Copy `Config/Publication.local.xcconfig.example` to its ignored local name and
supply the published website and corresponding-source URLs. The store settings
screen links to privacy, support and source pages supplied by its Info.plist.
`scripts/check-store-bundle.py` validates the built host binaries, publication
links and privacy manifests. During archiving it also requires a clean committed
source tree and verifies both embedded kernels against their accepted descriptors.
The store configuration runs the guest only in the foreground and has no audio
background mode.

The App Store configuration alone does not establish release readiness: an
archive must use accepted artifacts matching the archived inputs, and the
separately distributed guest software requires its applicable notices and corresponding source.
