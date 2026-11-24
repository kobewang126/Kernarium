#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise Ubuntu Touch policy artifacts and conservative overlay migration."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from unittest.mock import patch

sys.dont_write_bytecode = True


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def unpack(data):
    result = {}
    offset = 0
    while offset < len(data):
        if not data[offset]:
            offset += 1
            continue
        assert data[offset:offset + 6] == b'070701'
        fields = [int(data[offset + 6 + i * 8:offset + 14 + i * 8], 16)
                  for i in range(13)]
        name = data[offset + 110:offset + 110 + fields[11] - 1].decode()
        offset = (offset + 110 + fields[11] + 3) & ~3
        content = data[offset:offset + fields[6]]
        offset = (offset + fields[6] + 3) & ~3
        if name != 'TRAILER!!!':
            result[name] = content
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--producer', type=Path, required=True)
    parser.add_argument('--initramfs', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.producer / 'gpu-compat'))
    from artifact import read_artifact
    from build import source_inputs
    configure = load('configure_gpu', args.producer / 'configure-gpu.py')
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        artifact = root / 'artifact'
        (artifact / 'lib').mkdir(parents=True)
        library = bytearray(64)
        library[:6] = b'\x7fELF\x02\x01'
        library[18:20] = (183).to_bytes(2, 'little')
        lib = artifact / 'lib/libtoucharium-mir-gpu.so'
        lib.write_bytes(library)
        receipt = {'schema_version': 1, 'architecture': 'aarch64',
                   'inputs': source_inputs(),
                   'library_sha256': hashlib.sha256(library).hexdigest()}
        (artifact / 'receipt.json').write_text(json.dumps(receipt))
        for mode in ['ios', 'ubuntu']:
            output = root / (mode + '.cpio')
            subprocess.run([sys.executable, '-B', str(args.producer / 'build-policy.py'),
                            '--gpu-compat', str(artifact), '--initramfs', str(args.initramfs),
                            '--keyboard-source', mode, '--output', str(output)],
                           check=True, timeout=30)
            files = unpack(output.read_bytes())
            assert files['payload/etc/toucharium/keyboard-source'].decode().strip() == mode
            renderer = files['payload/etc/systemd/user/lomiri-app-launch--application-.service.d/90-toucharium-renderer.conf']
            assert b'QT_QPA_PLATFORM=ubuntumirclient' in renderer
            assert b'LIBGL_ALWAYS_SOFTWARE=0' in renderer
            assert not any('/qt5/plugins/' in name for name in files)
            assert files['payload/usr/lib/aarch64-linux-gnu/libtoucharium-mir-gpu.so'] == library
        lib.write_bytes(bytes(library) + b'tamper')
        try:
            read_artifact(artifact)
        except ValueError:
            pass
        else:
            raise AssertionError('tampered library accepted')
        lib.write_bytes(library)
        receipt['inputs'] = {}
        (artifact / 'receipt.json').write_text(json.dumps(receipt))
        try:
            read_artifact(artifact)
        except ValueError:
            pass
        else:
            raise AssertionError('stale source identity accepted')
        guest = root / 'guest'
        policy = guest / 'etc/toucharium'
        policy.mkdir(parents=True)
        mesa = guest / 'usr/lib/mesa.so'
        mesa.parent.mkdir(parents=True)
        mesa.write_bytes(b'pinned')
        owned = guest / 'usr/lib/old-plugin.so'
        changed = guest / 'usr/lib/changed-plugin.so'
        owned.write_bytes(b'old')
        changed.write_bytes(b'user update')
        digest = lambda data: hashlib.sha256(data).hexdigest()
        (policy / 'mesa.json').write_text(json.dumps({'libraries': {'usr/lib/mesa.so': digest(b'pinned')}}))
        (policy / 'legacy-wayland.json').write_text(json.dumps({'files': {
            'usr/lib/old-plugin.so': digest(b'old'),
            'usr/lib/changed-plugin.so': digest(b'old')}}))
        profiles = guest / 'var/lib/apparmor/profiles'
        profiles.mkdir(parents=True)
        (profiles / 'click_example').write_text('fixture')
        mapped = lambda name: guest / str(name).lstrip('/')
        with patch.object(configure, 'Path', mapped), patch.object(configure.subprocess, 'run') as run:
            configure.main()
            assert not owned.exists() and changed.read_bytes() == b'user update'
            assert run.call_count == 1
            owned.write_bytes(b'old')
            mesa.write_bytes(b'unsupported')
            try:
                configure.main()
            except RuntimeError:
                pass
            else:
                raise AssertionError('unsupported Mesa accepted')
            assert owned.exists(), 'migration ran before Mesa identity validation'
    print('Ubuntu Touch policy: both keyboard modes, native GPU payload, receipt rejection and conservative migration passed')


if __name__ == '__main__':
    main()
