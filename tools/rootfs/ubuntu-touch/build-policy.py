#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build the application-owned Ubuntu Touch boot policy without network access."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import tempfile

from setup import install_runtime_policy


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpu-compat", type=Path, required=True)
    parser.add_argument("--initramfs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--keyboard-source", choices=("ios", "ubuntu"), default="ios")
    options = parser.parse_args()
    source = Path(__file__).resolve().parent
    import sys
    sys.path.insert(0, str(source / 'gpu-compat'))
    from artifact import read_artifact
    library = read_artifact(options.gpu_compat)
    with tempfile.TemporaryDirectory(prefix="toucharium-policy-") as temporary:
        root = Path(temporary)
        install_runtime_policy(root, native_gpu=True)
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
        target = root / "usr/lib/aarch64-linux-gnu/libtoucharium-mir-gpu.so"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(library)
        target.chmod(0o644)
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
