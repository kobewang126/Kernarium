#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build the application-owned Ubuntu Touch boot policy without network access."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import tempfile

from setup import install_runtime_policy
from keyboard import install as install_keyboard


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpu-compat", type=Path)
    parser.add_argument("--initramfs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--keyboard-source", choices=("ios", "ubuntu"), default="ios")
    parser.add_argument("--shell-mode", choices=("phone", "desktop"), default="phone")
    parser.add_argument("--mode", choices=("full", "dynamic"), default="full")
    options = parser.parse_args()
    source = Path(__file__).resolve().parent
    library = None
    if options.mode == 'full':
        if options.gpu_compat is None:
            parser.error('--gpu-compat is required for a full policy')
        import sys
        sys.path.insert(0, str(source / 'gpu-compat'))
        from artifact import read_artifact
        library = read_artifact(options.gpu_compat)
    with tempfile.TemporaryDirectory(prefix="toucharium-policy-") as temporary:
        root = Path(temporary)
        interface = root / 'etc/systemd/user/lomiri-full-greeter.service.d/90-toucharium-interface.conf'
        interface.parent.mkdir(parents=True, exist_ok=True)
        usage = 'Windowed' if options.shell_mode == 'desktop' else 'Staged'
        interface.write_text('# SPDX-License-Identifier: GPL-2.0-or-later\n[Service]\n'
                             'ExecStartPre=/usr/bin/gsettings set com.lomiri.Shell usage-mode ' + usage + '\n')
        interface.chmod(0o644)
        if options.mode == 'full':
            install_runtime_policy(root, native_gpu=True)
        if options.mode == 'dynamic':
            target = root / 'etc/toucharium/keyboard-source'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(options.keyboard_source + '\n')
            target.chmod(0o644)
            # switch_root enters the image before running Python: the small
            # accepted BusyBox base does not include the chroot applet.
            entry = root / 'usr/libexec/toucharium-boot'
            entry.parent.mkdir(parents=True, exist_ok=True)
            entry.write_text('#!/bin/sh\n# SPDX-License-Identifier: GPL-2.0-or-later\n'
                             'set -eu\n'
                             '/usr/bin/python3 /.uml-lower/usr/lib/toucharium/migrate-image.py\n'
                             'exec /sbin/init "$@"\n')
            entry.chmod(0o755)
        if options.mode == 'full':
            install_keyboard(root, options.keyboard_source)
            target = root / "usr/lib/aarch64-linux-gnu/libtoucharium-mir-gpu.so"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(library)
            target.chmod(0o644)
        generated = root / "policy.cpio"
        command = [str(options.initramfs.resolve()),
                   "--output=" + str(generated)]
        command += ["--file=/payload/" + str(path.relative_to(root)) + "=" + str(path)
                    for path in sorted(root.rglob("*")) if path.is_file()]
        if options.mode == 'dynamic':
            # The runtime appends this segment after its generic /init. Run
            # migration while systemd is absent and the read-only lower is
            # visible; no mounted overlay layer is modified behind overlayfs.
            base = (source.parent / 'boot-ramdisk/init').read_text()
            anchor = 'echo "UML_BOOT_SWITCH_ROOT:$entry"'
            if base.count(anchor) != 1:
                raise ValueError('boot entry anchor is not unique')
            hook = ('[ -f /newroot/.uml-lower/usr/lib/toucharium/image-policy.json ] || '
                    'fail "Toucharium requires a version 2 image"\n'
                    'entry=/usr/libexec/toucharium-boot\n')
            init = Path(temporary) / 'init'
            init.write_text(base.replace(anchor, hook + anchor))
            init.chmod(0o755)
            command.append('--file=/init=' + str(init))
        subprocess.run(command, check=True, timeout=30)
        options.output.parent.mkdir(parents=True, exist_ok=True)
        generated.chmod(0o644)
        generated.replace(options.output)


if __name__ == "__main__":
    main()
