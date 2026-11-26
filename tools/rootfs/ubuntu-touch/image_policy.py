# SPDX-License-Identifier: GPL-2.0-or-later
"""Install the fixed, versioned Ubuntu Touch policy into an image."""
from pathlib import Path
import hashlib
import json
import sys

from setup import install_runtime_policy, write
from keyboard import install as install_keyboard
from display_policy import render_shell

SOURCE = Path(__file__).resolve().parent


def install(root: Path, gpu_compat: Path) -> dict:
    sys.path.insert(0, str(SOURCE / 'gpu-compat'))
    from artifact import read_artifact
    library = read_artifact(gpu_compat)
    pin = json.loads((SOURCE / 'sources.json').read_text())['lomiri_shell']
    shell = root / pin['path']
    write(root, pin['path'], render_shell(shell.read_bytes(), 8))
    # Produce the same fixed policy in isolation to enumerate only owned files.
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        policy = Path(directory)
        install_runtime_policy(policy, native_gpu=True)
        install_keyboard(policy)
        write(policy, 'usr/lib/aarch64-linux-gnu/libtoucharium-mir-gpu.so', '')
        (policy / 'usr/lib/aarch64-linux-gnu/libtoucharium-mir-gpu.so').write_bytes(library)
        write(policy, 'usr/lib/toucharium/migrate-image.py', (SOURCE / 'migrate-image.py').read_text(), 0o755)
        legacy = json.loads((SOURCE / 'legacy-policy.json').read_text())
        files = {}
        for path in sorted(policy.rglob('*')):
            if not path.is_file():
                continue
            name = str(path.relative_to(policy))
            data = path.read_bytes()
            target = root / name
            write(root, name, '', path.stat().st_mode & 0o777)
            target.write_bytes(data)
            # Display and keyboard selections remain app-owned boot parameters.
            if name in ('etc/toucharium/keyboard-source', 'etc/deviceinfo/default.yaml',
                        'etc/ubuntu-touch-session.d/android.conf'):
                continue
            files[name] = {'sha256': hashlib.sha256(data).hexdigest(),
                           'mode': path.stat().st_mode & 0o777,
                           'previous_sha256': legacy.get(name, [])}
        manifest = {'schema_version': 1, 'policy_version': 2, 'files': files}
        write(root, 'usr/lib/toucharium/image-policy.json', json.dumps(manifest, indent=2) + '\n')
        return manifest
