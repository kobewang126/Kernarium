#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise Ubuntu Touch policy artifacts and conservative overlay migration."""
from pathlib import Path
import argparse
import configparser
import hashlib
import importlib.util
import json
import lzma
import subprocess
import shutil
import sys
import tempfile
from types import SimpleNamespace
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


def check_local_packaging(producer: Path, root: Path):
    package = load('local_package', producer / 'package.py')
    information = subprocess.run([sys.executable, '-B', str(producer / 'package.py')],
                                 check=True, capture_output=True, text=True, timeout=10)
    pin = json.loads((producer / 'sources.json').read_text())['archive']
    assert pin['url'] in information.stdout and pin['sha256'] in information.stdout
    payload = b'official input fixture\n' * 1024
    expected = hashlib.sha256(payload).hexdigest()
    archive = root / 'disk.raw.xz'
    archive.write_bytes(lzma.compress(payload))
    disk = root / 'disk.raw'
    package.decompress(archive, disk, len(payload), expected)
    assert disk.read_bytes() == payload and archive.exists()
    package.decompress(archive, disk, len(payload), expected)
    rejected = root / 'rejected.raw'
    for size, checksum in [(len(payload) - 1, expected), (len(payload), '0' * 64)]:
        try:
            package.decompress(archive, rejected, size, checksum)
        except ValueError:
            pass
        else:
            raise AssertionError('unverified raw disk was published')
        assert not rejected.exists() and not list(root.glob('.raw-*'))


def check_packaging_hosts(producer: Path, root: Path, artifact: Path):
    root, artifact = root.resolve(), artifact.resolve()
    package = load('package_hosts', producer / 'package.py')
    import derive
    source = root / 'package-source'
    source.mkdir()
    raw = root / 'host-fixture.raw'
    raw.write_bytes(b'verified offline input')
    pin = json.loads((producer / 'sources.json').read_text())
    pin['disk']['size'] = raw.stat().st_size
    pin['disk']['sha256'] = hashlib.sha256(raw.read_bytes()).hexdigest()
    (source / 'sources.json').write_text(json.dumps(pin))
    for architecture in ['aarch64', 'x86_64']:
        for explicit in [True, False]:
            work = root / f'package-{architecture}-{explicit}'
            work.mkdir()
            gpu = artifact if explicit else work / 'gpu-compat'
            if not explicit:
                shutil.copytree(artifact, gpu)
            output = work / 'local.erofs'
            arguments = ['package.py', '--disk', str(raw), '--work', str(work), '--output', str(output)]
            if explicit:
                arguments += ['--gpu-compat', str(gpu)]

            def produce():
                assert sys.argv[sys.argv.index('--disk') + 1] == str(raw)
                assert sys.argv[sys.argv.index('--gpu-compat') + 1] == str(gpu)
                output.write_bytes(b'producer fixture')
                output.with_suffix('.erofs.json').write_text('{}')

            def accept(command, **kwargs):
                assert Path(command[2]).name == 'accept-image.py', 'guest code was compiled or executed'
                assert command[command.index('--image') + 1] == str(output)
                Path(command[command.index('--catalog') + 1]).write_text('{}')
                return subprocess.CompletedProcess(command, 0)

            with patch.object(package, 'DIRECTORY', source), \
                    patch.object(package.platform, 'system', return_value='Linux'), \
                    patch.object(package.platform, 'machine', return_value=architecture), \
                    patch.object(package.platform, 'libc_ver', return_value=('glibc', '2.43')), \
                    patch.object(package.os, 'geteuid', return_value=0), \
                    patch.object(package.shutil, 'disk_usage', return_value=SimpleNamespace(free=64 << 30)), \
                    patch.object(package.shutil, 'which', side_effect=lambda name:
                                 '/tool/' + name if name in ['mount', 'umount', 'mkfs.erofs', 'fsck.erofs'] else None), \
                    patch.object(derive, 'main', side_effect=produce), \
                    patch.object(package.subprocess, 'run', side_effect=accept) as commands, \
                    patch.object(sys, 'argv', arguments):
                package.main()
                assert commands.call_count == 1
            assert raw.read_bytes() == b'verified offline input'
            assert output.exists() and output.with_suffix('.erofs.import.json').exists()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--producer', type=Path, required=True)
    parser.add_argument('--initramfs', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.producer / 'gpu-compat'))
    from artifact import read_artifact
    from build import source_inputs
    configure = load('configure_gpu', args.producer / 'configure-gpu.py')
    locale_policy = load('configure_locale', args.producer / 'configure-locale.py')
    migration = load('migrate_image', args.producer / 'migrate-image.py')
    sys.path.insert(0, str(args.producer))
    display = load('display_selection', args.producer / 'build-display-policy.py')
    try:
        display.render_mode(b'wrong upstream source', 'desktop')
    except ValueError:
        pass
    else:
        raise AssertionError('unverified usage mode source accepted')
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        check_local_packaging(args.producer, root)
        selected = root / 'display-selection'
        selected.mkdir()
        display.install_selection(selected, 16, 'phone')
        assert 'PrimaryOrientation: Portrait' in (selected / 'etc/deviceinfo/default.yaml').read_text()
        display.install_selection(selected, 16, 'desktop')
        device = (selected / 'etc/deviceinfo/default.yaml').read_text()
        legacy = (selected / 'etc/ubuntu-touch-session.d/android.conf').read_text()
        assert 'DeviceType: desktop' in device and 'GridUnit: 16' in device
        assert 'Orientation' not in device and 'phone:' not in device
        assert 'FORM_FACTOR=desktop' in legacy and 'NATIVE_ORIENTATION' not in legacy
        assert 'QTWEBKIT_DPR=2' in legacy
        display.install_selection(selected, 16, 'phone')
        assert 'FORM_FACTOR=handset' in (selected / 'etc/ubuntu-touch-session.d/android.conf').read_text()
        locale_file = root / 'locale'
        for original in ['#LANG=C.UTF-8\n', '', 'LANG=""\n']:
            locale_file.write_text(original)
            locale_policy.configure(locale_file)
            assert locale_file.read_text().endswith('LANG=C.UTF-8\n')
            installed = locale_file.read_bytes()
            locale_policy.configure(locale_file)
            assert locale_file.read_bytes() == installed
        locale_file.write_text('LANG="de_DE.UTF-8"\n')
        locale_policy.configure(locale_file)
        assert locale_file.read_text() == 'LANG="de_DE.UTF-8"\n'
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
            locale = dict(line.split('=', 1) for line in
                          files['payload/etc/default/locale'].decode().splitlines()
                          if line and not line.startswith('#'))
            assert locale['LANG'] == 'C.UTF-8'
            input_service = configparser.ConfigParser(interpolation=None)
            input_service.read_string(files['payload/etc/systemd/system/toucharium-input.service'].decode())
            assert input_service['Service']['Restart'] == 'on-failure'
            assert input_service['Unit']['StartLimitIntervalSec'] == '0'
            assert int(input_service['Service']['TimeoutStartSec']) > 135
            display_service = configparser.ConfigParser(interpolation=None)
            display_service.read_string(files['payload/etc/systemd/system/toucharium-display.service'].decode())
            assert display_service['Service']['ExecStart'] == '/usr/sbin/repowerd-cli display on'
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
        check_packaging_hosts(args.producer, root, artifact)
        # The app's dynamic archive contains no fixed guest implementation.
        for shell_mode, usage in [('phone', 'Staged'), ('desktop', 'Windowed')]:
            dynamic = root / (shell_mode + '.cpio')
            subprocess.run([sys.executable, '-B', str(args.producer / 'build-policy.py'),
                            '--initramfs', str(args.initramfs), '--shell-mode', shell_mode,
                            '--mode', 'dynamic', '--output', str(dynamic)], check=True, timeout=30)
            dynamic_files = unpack(dynamic.read_bytes())
            interface = 'payload/etc/systemd/user/lomiri-full-greeter.service.d/90-toucharium-interface.conf'
            assert set(dynamic_files) == {'init', 'payload', 'payload/etc', 'payload/etc/toucharium',
                                          'payload/etc/toucharium/keyboard-source', 'payload/usr',
                                          'payload/usr/libexec', 'payload/usr/libexec/toucharium-boot',
                                          'payload/etc/systemd', 'payload/etc/systemd/user',
                                          'payload/etc/systemd/user/lomiri-full-greeter.service.d', interface}
            unit = configparser.ConfigParser(interpolation=None)
            unit.read_string(dynamic_files[interface].decode())
            assert unit['Service']['ExecStartPre'].split() == [
                '/usr/bin/gsettings', 'set', 'com.lomiri.Shell', 'usage-mode', usage]
            subprocess.run(['/bin/sh', '-n'], input=dynamic_files['init'], check=True, timeout=10)
            subprocess.run(['/bin/sh', '-n'], input=dynamic_files['payload/usr/libexec/toucharium-boot'],
                           check=True, timeout=10)

        lower, running = root / 'lower', root / 'running'
        lower.mkdir()
        running.mkdir()
        managed = 'etc/example.conf'
        custom = 'etc/custom.conf'
        user_data = running / 'home/phablet/document'
        user_data.parent.mkdir(parents=True)
        user_data.write_bytes(b'keep user data')
        files = {}
        for name in [managed, custom]:
            (lower / name).parent.mkdir(parents=True, exist_ok=True)
            (lower / name).write_bytes(b'new policy')
            (running / name).parent.mkdir(parents=True, exist_ok=True)
            files[name] = {'sha256': migration.digest(b'new policy'), 'mode': 0o644,
                           'previous_sha256': [migration.digest(b'old policy')]}
        (running / managed).write_bytes(b'old policy')
        (running / custom).write_bytes(b'custom policy')
        manifest = lower / 'usr/lib/toucharium/image-policy.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({'schema_version': 1, 'policy_version': 2, 'files': files}))
        assert migration.migrate(running, lower) == [custom]
        assert (running / managed).read_bytes() == b'new policy'
        assert (running / custom).read_bytes() == b'custom policy'
        assert user_data.read_bytes() == b'keep user data'
        saved = list((running / 'var/lib/toucharium/migrations').glob('*/files/etc/example.conf'))
        assert len(saved) == 1 and saved[0].read_bytes() == b'old policy'
        assert migration.migrate(running, lower) == [custom]
        marker = next((running / 'var/lib/toucharium/migrations').glob('*/complete.json'))
        for damaged in ['', '{', '{}', '{"preserved": null}']:
            marker.write_text(damaged)
            assert migration.migrate(running, lower) == [custom]
            assert json.loads(marker.read_text()) == {'preserved': [custom]}
            assert saved[0].read_bytes() == b'old policy'
            assert user_data.read_bytes() == b'keep user data'
        marker.unlink()
        (running / managed).unlink()
        (running / managed).symlink_to(user_data)
        assert set(migration.migrate(running, lower)) == {managed, custom}
        assert (running / managed).is_symlink()
        assert user_data.read_bytes() == b'keep user data'
        marker.unlink()
        (running / managed).unlink()
        (running / 'etc').rename(running / 'redirected-etc')
        (running / 'etc').symlink_to(running / 'redirected-etc', target_is_directory=True)
        assert set(migration.migrate(running, lower)) == {managed, custom}
        assert (running / 'etc').is_symlink()
        assert (running / 'redirected-etc/custom.conf').read_bytes() == b'custom policy'
        for invalid in ['../escape', '/etc/escape']:
            try:
                migration.resolve(running, invalid)
            except ValueError:
                pass
            else:
                raise AssertionError('unsafe migration path accepted')
        (lower / managed).write_bytes(b'tampered')
        fresh = root / 'fresh'
        fresh.mkdir()
        try:
            migration.migrate(fresh, lower)
        except ValueError:
            pass
        else:
            raise AssertionError('tampered policy accepted')
        assert list(fresh.iterdir()) == [], 'migration wrote before validating its inputs'
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
