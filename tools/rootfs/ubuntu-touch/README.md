# Ubuntu Touch guest image

This producer adapts the pinned official UBports arm64 PDK image for the
Kernarium virtual devices. It preserves Ubuntu Touch's Lomiri, LightDM system
compositor session, extrausers account and application services. The policy
removes PDK-specific host mounts and boot-partition UUIDs and grants the
phablet session access to the virtual graphics and input devices.
DeviceInfo identifies the virtual device as a portrait phone; the legacy
session configuration carries the same phone policy.
The system locale defaults to C.UTF-8 so AccountsService can complete the
first language selection; the selected user's locale remains in their home.
An AccountsService prerequisite restores a missing default after local
filesystems are mounted and preserves an existing locale selection.
The input service maps the virtual touchscreen to the active display wall in
both the system compositor and Lomiri's nested Mir server after LightDM
activates input devices, and runs again when LightDM restarts.
Failed mapping attempts retry with a bounded timeout per attempt, including
when Mir discovers input devices late during the first session.
The version 2 EROFS image embeds the fixed runtime policy, guest keyboard
implementation, native Mir GPU compatibility library and default display
patch. Its receipt identifies all producer inputs and the immutable policy
manifest. `derive.py` verifies the compatibility artifact before installation.
`build-policy.py --mode dynamic` packages only the selected keyboard and shell modes and
migration bootstrap; the application appends its display-density override.
The full archive mode remains available for policy verification.

The image's managed-file manifest records current digests and the recognized
1.1 policy digests in `legacy-policy.json`. Before systemd starts, migration
verifies all immutable source files, backs up and replaces recognized old
policy files through the merged filesystem, and preserves unknown custom
contents and writable-path symbolic links. It never edits the raw upper layer behind overlayfs, clears user
data, or resets the overlay. Migration results and backups stay in the guest's
`/var/lib/toucharium/migrations` directory. Repeating a completed migration does
not rewrite guest files. Completion is published atomically after file writes
are synchronized; an incomplete completion record is recovered on the next boot.

The graphics startup service checks the guest Mesa library digests, removes
only unchanged client plugins installed by the legacy policy, and reloads
application access to the virtual GPU device information. System Wayland
libraries remain part of the image. The compatibility library temporarily
completes the Mir platform image callbacks for the pinned Mesa ABI; its owner
and canonical build entry point are in [`gpu-compat`](gpu-compat/README.md).
The app policy selects iPhone or Ubuntu keyboard mode at boot. Its user-service
drop-in sets Lomiri to Staged or Windowed mode before the shell starts; the
display archive selects the phone layout for Staged and a desktop device
profile without a forced native orientation for Windowed. The mode-specific
OrientedShell override preserves the explicit choice when pointer devices are
added or removed, including on touch-only devices.
`build-display-policy.py` packages display-density overrides separately from
the plugins. The app appends the override matching the boot display density,
keeping Lomiri's grid-unit and web-content density aligned with Retina.
The display producer verifies the pinned Shell and OrientedShell sources.
The display override checks the pinned rootfs's original Lomiri Shell digest
and keeps its Units object at the selected grid unit when QtMir reports the
virtual connector at native scale one. Mir's coordinates and application
rendering policy retain their existing scale.
Maliit's service applies the selected visibility policy after the Lomiri user
bus starts; switching modes takes effect on the next application launch.

The producer scripts are GPL-2.0-or-later. `lomiri-grid-unit.qml.in` is the
GPL-3.0-only fragment inserted into the pinned Lomiri Shell, whose copyright
and licence notices are preserved. The output image and boot archives contain
components under their individual licences; repackaging does not relicense
them. Their binary distribution requires the applicable notices and exact
corresponding sources. The upstream image digest is an input identity, not a
substitute for those sources.

`sources.json` pins the official archive and raw disk. Running `package.py`
without an input prints the official download URL and archive SHA-256, including
on macOS. The user downloads that file in their browser. Packaging then verifies
the archive and decompressed disk, extracts the embedded ARM64 GPU compatibility library,
and invokes the image producer. The script does not access the network or modify
the supplied input. Verified decompressed inputs are cached for later runs.

Run on ARM64 or x86-64 Linux as root, with Python 3, erofs-utils,
and the system mount utilities installed:

```sh
sudo python3 tools/rootfs/ubuntu-touch/package.py \
  --archive /path/to/ubuntu-touch-pdk-img-arm64.raw.xz \
  --work /path/to/local-work \
  --output /path/to/ubuntu-touch-local.erofs
```

The first run needs space for the official raw disk plus packaging scratch;
macOS requires a Linux VM. A work directory admits one packaging process at a
time. Existing outputs are refused. Both host architectures use the same
embedded library, whose source identity, ARM64 ELF header and digest are
verified before use. Packaging does not compile or execute guest code and
does not require a C++ compiler, CMake or Ninja. The produced guest remains
ARM64 on either host architecture. `--disk`
accepts an already decompressed official input instead of an archive.
`derive.py` remains the offline producer for already decompressed inputs.

The output is the EROFS image, its producer receipt and an adjacent
`.erofs.import.json` application descriptor. The current application accepts
only its bundled descriptor: locally generated images require matching import
support or an application build accepting that generated descriptor. Local
repacking alone does not make an image accepted by an existing application.

`accept-image.py` verifies the completed image and current producer receipt
before generating the application's import descriptor:

```sh
python3 tools/rootfs/ubuntu-touch/accept-image.py \
  --image /path/to/ubuntu-touch-pdk-470-v2-r3.erofs \
  --receipt /path/to/ubuntu-touch-pdk-470-v2-r3.erofs.json \
  --catalog Toucharium/Sources/TouchariumImage.json
```

The input remains read-only. The producer verifies its size and digest, applies
the policy through overlayfs, checks the EROFS output and writes a receipt beside
it. Existing outputs are refused. Image import verifies the accepted full-file
SHA-256 before the application starts a guest; an imported image alone does not
prove that the Ubuntu Touch session has booted.

Upstream sources: [UBports PDK](https://github.com/ubports/ubports-pdk) and the
[pinned rootfs build](https://ci.ubports.com/job/ubuntu-touch-rootfs/job/ubports%252F24.04-1.x/470/).
