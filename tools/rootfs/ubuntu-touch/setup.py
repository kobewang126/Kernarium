#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Install the Kernarium virtual-device policy into an Ubuntu Touch root."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def write(root: Path, name: str, text: str, mode: int = 0o644) -> None:
    target = root / name
    # Never follow an image's absolute symlink into the build host.
    parent = root
    for part in Path(name).parts[:-1]:
        parent /= part
        if parent.is_symlink():
            raise ValueError(f"policy directory is a symlink: {parent}")
        parent.mkdir(exist_ok=True)
    if target.is_symlink():
        target.unlink()
    target.write_text(text)
    target.chmod(mode)


def mask(root: Path, unit: str) -> None:
    target = root / "etc/systemd/system" / unit
    if target.exists() or target.is_symlink():
        target.unlink()
    target.symlink_to("/dev/null")


def apply(root: Path) -> None:
    if root == Path("/"):
        raise ValueError("refusing the build host's root filesystem")
    release = (root / "etc/os-release").read_text()
    if "VARIANT_ID=touch" not in release:
        raise ValueError("source is not an Ubuntu Touch root filesystem")
    for path in ("usr/bin/lomiri", "usr/sbin/ubuntu-touch-lightdm-session",
                 "usr/lib/aarch64-linux-gnu/mir1/server-platform/graphics-mesa-kms.so.16"):
        if not (root / path).is_file():
            raise ValueError(f"Ubuntu Touch PDK component is missing: {path}")

    # The boot ramdisk mounts the selected root. The source's EFI and boot
    # partitions and UUIDs do not exist in the virtual-device guest.
    write(root, "etc/fstab", "# Root is mounted by the Kernarium boot ramdisk.\n")
    mask(root, "ubports-pdk-mount.service")
    for unit in ("getty@tty0.service", "getty@tty1.service"):
        mask(root, unit)
    write(root, "etc/machine-id", "")
    machine_id = root / "var/lib/dbus/machine-id"
    if machine_id.exists() or machine_id.is_symlink():
        machine_id.unlink()
    machine_id.symlink_to("../../../etc/machine-id")
    write(root, "etc/hostname", "toucharium\n")
    write(root, "etc/hosts", "127.0.0.1 localhost\n127.0.1.1 toucharium\n::1 localhost ip6-localhost ip6-loopback\n")

    # phablet is an extrausers account in Ubuntu Touch, not an /etc/passwd
    # account. Preserve it and extend the existing device groups directly.
    groups = (root / "etc/group").read_text().splitlines()
    for index, line in enumerate(groups):
        fields = line.split(":")
        if len(fields) == 4 and fields[0] in {"video", "render", "input"}:
            members = fields[3].split(",") if fields[3] else []
            if "phablet" not in members:
                members.append("phablet")
            fields[3] = ",".join(members)
            groups[index] = ":".join(fields)
    write(root, "etc/group", "\n".join(groups) + "\n")
    install_runtime_policy(root)
    write(root, "etc/NetworkManager/system-connections/toucharium.nmconnection", '''# SPDX-License-Identifier: GPL-2.0-or-later
[connection]
id=Toucharium Ethernet
type=ethernet
autoconnect=true
[ethernet]
[ipv4]
method=auto
[ipv6]
method=auto
''', 0o600)
    write(root, "etc/toucharium-release", "SOURCE=ubuntu-touch-24.04-1.x-pdk-470-arm64\n")


def install_display_policy(root: Path, grid_unit: int = 8) -> None:
    if not 8 <= grid_unit <= 64:
        raise ValueError("display grid unit must be between 8 and 64")
    webkit_dpr = grid_unit / 8
    write(root, "etc/deviceinfo/default.yaml", f'''# SPDX-License-Identifier: GPL-2.0-or-later
defaults:
  default:
    Name: toucharium
    PrettyName: Toucharium
    DeviceType: phone
    GridUnit: {grid_unit}
    WebkitDpr: {webkit_dpr:g}
    PrimaryOrientation: Portrait
    PortraitOrientation: Portrait
    InvertedPortraitOrientation: InvertedPortrait
    LandscapeOrientation: Landscape
    InvertedLandscapeOrientation: InvertedLandscape
    SupportedOrientations:
      - Portrait
      - InvertedPortrait
      - Landscape
      - InvertedLandscape
  phone:
    GridUnit: {grid_unit}
    WebkitDpr: {webkit_dpr:g}
    PrimaryOrientation: Portrait
''')
    # DeviceInfo still imports this legacy file on the native Linux PDK.
    # Its VM form factor otherwise selects Lomiri's desktop window manager.
    write(root, "etc/ubuntu-touch-session.d/android.conf", f'''# SPDX-License-Identifier: GPL-2.0-or-later
GRID_UNIT_PX={grid_unit}
QT_AUTO_SCREEN_SCALE_FACTOR=1
QTWEBKIT_DPR={webkit_dpr:g}
NATIVE_ORIENTATION=Portrait
FORM_FACTOR=handset
''')


def install_runtime_policy(root: Path, *, native_gpu: bool = False) -> None:
    install_display_policy(root)
    write(root, "etc/udev/rules.d/70-toucharium-virtual-devices.rules", '''# SPDX-License-Identifier: GPL-2.0-or-later
SUBSYSTEM=="drm", KERNEL=="card[0-9]*", GROUP="video", MODE="0660", TAG+="uaccess", TAG+="seat"
SUBSYSTEM=="drm", KERNEL=="renderD[0-9]*", GROUP="render", MODE="0660", TAG+="uaccess"
SUBSYSTEM=="input", KERNEL=="event[0-9]*", GROUP="input", MODE="0660", TAG+="uaccess"
''')
    # Keep the PDK's Ubuntu Touch LightDM -> system compositor -> Lomiri
    # session. Mir's KMS probe needs the same override as on QEMU/KVM.
    write(root, "etc/default/lsc-wrapper.d/90-toucharium.conf", '''# SPDX-License-Identifier: GPL-2.0-or-later
export MIR_MESA_KMS_DISABLE_MODESET_PROBE=1
''')
    write(root, "usr/libexec/toucharium-configure-input",
          (Path(__file__).resolve().parent / "configure-input.py").read_text(), 0o755)
    # Mir enumerates input devices after LightDM activates its user session.
    # A synchronous LightDM setup hook would prevent that activation.
    write(root, "etc/systemd/system/toucharium-input.service", '''# SPDX-License-Identifier: GPL-2.0-or-later
[Unit]
Description=Configure the Toucharium virtual touchscreen
Requires=lightdm.service
After=lightdm.service
PartOf=lightdm.service

[Service]
Type=oneshot
ExecStart=/usr/libexec/toucharium-configure-input
TimeoutStartSec=140
RemainAfterExit=yes
''')
    write(root, "etc/systemd/system/lightdm.service.d/95-toucharium-input.conf", '''# SPDX-License-Identifier: GPL-2.0-or-later
[Unit]
Wants=toucharium-input.service toucharium-display.service
''')
    # The Apple host owns screen sleep. Letting repowerd blank the virtual
    # output also removes Mir's active input devices while mapping starts.
    write(root, "etc/systemd/system/toucharium-display.service", '''# SPDX-License-Identifier: GPL-2.0-or-later
[Unit]
Description=Keep the Toucharium virtual display available to its host
Wants=repowerd.service
After=repowerd.service lightdm.service
PartOf=lightdm.service

[Service]
ExecStart=/usr/bin/repowerd-cli display on
Restart=on-failure
RestartSec=1
TimeoutStopSec=5
''')
    if native_gpu:
        source = Path(__file__).resolve().parent
        pin = json.loads((source / "sources.json").read_text())["mesa"]
        write(root, "etc/toucharium/mesa.json", json.dumps(pin) + "\n")
        write(root, "etc/toucharium/legacy-wayland.json",
              (source / "legacy-wayland.json").read_text())
        write(root, "usr/libexec/toucharium-configure-gpu",
              (source / "configure-gpu.py").read_text(), 0o755)
        write(root, "usr/share/apparmor/hardware/graphics.d/toucharium-virtio",
              "# SPDX-License-Identifier: GPL-2.0-or-later\n"
              "/sys/devices/virtio-uml-cmdline/virtio-uml.0/uevent r,\n")
        write(root, "etc/systemd/user/lomiri-app-launch--application-.service.d/90-toucharium-renderer.conf", """# SPDX-License-Identifier: GPL-2.0-or-later
[Service]
Environment=QT_QPA_PLATFORM=ubuntumirclient
Environment=LIBGL_ALWAYS_SOFTWARE=0
""")
        write(root, "etc/systemd/user/lomiri-full-greeter.service.d/99-toucharium-gpu.conf", """# SPDX-License-Identifier: GPL-2.0-or-later
[Service]
Environment=LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libtoucharium-mir-gpu.so
""")
        write(root, "etc/systemd/system/toucharium-gpu-policy.service", """# SPDX-License-Identifier: GPL-2.0-or-later
[Unit]
Description=Validate guest graphics and load virtual GPU access policy
After=apparmor.service
Before=lightdm.service
[Service]
Type=oneshot
ExecStart=/usr/libexec/toucharium-configure-gpu
TimeoutStartSec=120
RemainAfterExit=yes
""")
        write(root, "etc/systemd/system/lightdm.service.d/94-toucharium-gpu.conf", """# SPDX-License-Identifier: GPL-2.0-or-later
[Unit]
Requires=toucharium-gpu-policy.service
After=toucharium-gpu-policy.service
""")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    options = parser.parse_args()
    apply(options.root.resolve())


if __name__ == "__main__":
    main()
