#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Validate the guest Mesa ABI and load the virtual GPU application policy."""
from pathlib import Path
import hashlib
import json
import subprocess


def main():
    policy = Path('/etc/toucharium')
    pin = json.loads((policy / 'mesa.json').read_text())
    for name, expected in pin['libraries'].items():
        if hashlib.sha256((Path('/') / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError('unsupported guest Mesa library: ' + name)
    legacy = json.loads((policy / 'legacy-wayland.json').read_text())
    for name, expected in legacy['files'].items():
        path = Path('/') / name
        if path.is_file() and not path.is_symlink():
            if hashlib.sha256(path.read_bytes()).hexdigest() == expected:
                path.unlink()
    for profile in sorted(Path('/var/lib/apparmor/profiles').glob('click_*')):
        if profile.is_file():
            subprocess.run(['/usr/sbin/apparmor_parser', '-r', '--', str(profile)],
                           check=True, timeout=20)


if __name__ == '__main__':
    main()
