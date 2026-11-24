# Ubuntu Touch guest image

This producer adapts the pinned official UBports arm64 PDK image for the
Kernarium virtual devices. It preserves Ubuntu Touch's Lomiri, LightDM system
compositor session, extrausers account and application services. The policy
removes PDK-specific host mounts and boot-partition UUIDs and grants the
phablet session access to the virtual graphics and input devices.
DeviceInfo identifies the virtual device as a portrait phone; the legacy
session configuration carries the same phone policy.
The input service maps the virtual touchscreen to the active display wall in
both the system compositor and Lomiri's nested Mir server after LightDM
activates input devices, and runs again when LightDM restarts.
The input policy is embedded in the image and its digest is recorded in the
image receipt. `build-policy.py` packages the same policy with the pinned Qt
native Mir GPU configuration and a version-pinned Mesa compatibility library into a newc
archive. It verifies the library receipt and uses `uml-initramfs` to generate
the archive without network access. Toucharium embeds it and supplies it on
ordinary boots, so an installed application's policy can update an existing
persistent overlay before the Ubuntu session starts.
The graphics startup service checks the guest Mesa library digests, removes
only unchanged client plugins installed by the legacy policy, and reloads
application access to the virtual GPU device information. System Wayland
libraries remain part of the image. The compatibility library temporarily
completes the Mir platform image callbacks for the pinned Mesa ABI; its owner
and canonical build entry point are in [`gpu-compat`](gpu-compat/README.md).
The app policy selects iPhone or experimental Ubuntu keyboard mode at boot.
`build-display-policy.py` packages display-density overrides separately from
the plugins. The app appends the override matching the boot display density,
keeping Lomiri's grid-unit and web-content density aligned with Retina.
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

`sources.json` pins the official archive and raw disk. On Linux, decompress the
archive and run the producer as root with erofs-utils installed:

```sh
xz -dk ubuntu-touch-pdk-img-arm64.raw.xz
sudo python3 tools/rootfs/ubuntu-touch/derive.py \
  --disk ubuntu-touch-pdk-img-arm64.raw \
  --output /path/to/ubuntu-touch-pdk-470-r3.erofs \
  --work-root /path/to/linux-work
```

The input remains read-only. The producer verifies its size and digest, applies
the policy through overlayfs, checks the EROFS output and writes a receipt beside
it. Existing outputs are refused. The generic boot ramdisk mounts the image and
starts its own `/sbin/init`; the application's successful installation alone
does not prove that the Ubuntu Touch session has booted.

Upstream sources: [UBports PDK](https://github.com/ubports/ubports-pdk) and the
[pinned rootfs build](https://ci.ubports.com/job/ubuntu-touch-rootfs/job/ubports%252F24.04-1.x/470/).
