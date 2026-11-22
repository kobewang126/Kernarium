#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build the application-owned Ubuntu Touch boot policy without network access."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

from setup import install_runtime_policy


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qtwayland-deb", type=Path, required=True)
    parser.add_argument("--initramfs", type=Path, required=True)
    parser.add_argument("--zstd", default="zstd")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--keyboard-source", choices=("ios", "ubuntu"), default="ios")
    options = parser.parse_args()
    source = Path(__file__).resolve().parent
    pin = json.loads((source / "sources.json").read_text())["qtwayland"]
    data = options.qtwayland_deb.read_bytes()
    if hashlib.sha256(data).hexdigest() != pin["sha256"]:
        raise ValueError("Qt Wayland package digest does not match sources.json")
    if not data.startswith(b"!<arch>\n"):
        raise ValueError("Qt Wayland input is not a Debian archive")
    offset = 8
    payload = None
    while offset + 60 <= len(data):
        header = data[offset:offset + 60]
        size = int(header[48:58])
        name = header[:16].decode().strip().rstrip("/")
        offset += 60
        if name.startswith("data.tar"):
            payload = data[offset:offset + size]
            break
        offset += size + size % 2
    if payload is None:
        raise ValueError("Qt Wayland package has no data archive")
    if name.endswith(".zst"):
        payload = subprocess.run(
            [options.zstd, "--decompress", "--stdout"], input=payload,
            stdout=subprocess.PIPE, check=True, timeout=15).stdout
    with tempfile.TemporaryDirectory(prefix="toucharium-policy-") as temporary:
        root = Path(temporary)
        install_runtime_policy(root, software_opengl=True)
        # Apply after Lomiri establishes its user bus, including on later
        # logins. The image's PDK defaults suppress the OSK's height.
        files = {
            "etc/toucharium/keyboard-source": options.keyboard_source + "\n",
            "etc/systemd/user/maliit-server.service.d/90-toucharium-keyboard.conf":
                "# SPDX-License-Identifier: GPL-2.0-or-later\n"
                "[Service]\nExecStartPre=/usr/libexec/toucharium-configure-keyboard\n",
            "usr/libexec/toucharium-configure-keyboard":
                "#!/bin/sh\n# SPDX-License-Identifier: GPL-2.0-or-later\nset -eu\n"
                "case $(cat /etc/toucharium/keyboard-source) in\n"
                "ios) hidden=true; always=false ;;\n"
                "ubuntu) hidden=false; always=true ;;\n"
                "*) exit 1 ;;\nesac\n"
                "gsettings set com.lomiri.keyboard.maliit stay-hidden $hidden\n"
                "gsettings set com.lomiri.keyboard.maliit disable-height $hidden\n"
                "gsettings set com.lomiri.Shell always-show-osk $always\n",
        }
        for name, contents in files.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(contents)
            target.chmod(0o755 if name.startswith("usr/libexec/") else 0o644)
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
            for member in archive:
                name = member.name.removeprefix("./")
                if not member.isfile():
                    continue
                if ".." in Path(name).parts or name.startswith("/"):
                    raise ValueError("unsafe Qt Wayland package member")
                if not (name.startswith("usr/lib/aarch64-linux-gnu/qt5/plugins/")
                        and "/wayland-graphics-integration-server/" not in name
                        or name == "usr/share/doc/qtwayland5/copyright"):
                    continue
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                stream = archive.extractfile(member)
                assert stream is not None
                target.write_bytes(stream.read())
                target.chmod(member.mode & 0o777)
        plugin = root / "usr/lib/aarch64-linux-gnu/qt5/plugins/platforms/libqwayland-egl.so"
        if not plugin.is_file():
            raise ValueError("Qt Wayland EGL plugin is missing")
        generated = root / "policy.cpio"
        command = [str(options.initramfs.resolve()),
                   "--output=" + str(generated)]
        command += ["--file=/payload/" + str(path.relative_to(root)) + "=" + str(path)
                    for path in sorted(root.rglob("*")) if path.is_file()]
        subprocess.run(command, check=True, timeout=30)
        options.output.parent.mkdir(parents=True, exist_ok=True)
        generated.chmod(0o644)
        generated.replace(options.output)


if __name__ == "__main__":
    main()
