#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Show the official download URL and package a locally supplied UBports image."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import lzma
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlparse

from derive import digest

DIRECTORY = Path(__file__).resolve().parent


def publish(source: Path, destination: Path) -> None:
    # An interrupted or concurrent run must not replace an accepted input.
    os.link(source, destination)
    source.unlink()


def decompress(archive: Path, disk: Path, size: int, expected: str) -> None:
    if disk.exists():
        if disk.stat().st_size != size or digest(disk) != expected:
            raise ValueError('cached raw disk differs from the pinned official input')
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=disk.parent, prefix='.raw-', delete=False) as stream:
            temporary = Path(stream.name)
            checksum = hashlib.sha256()
            total = 0
            deadline = time.monotonic() + 1800
            with lzma.open(archive, 'rb') as source:
                while block := source.read(8 << 20):
                    total += len(block)
                    if total > size or time.monotonic() >= deadline:
                        raise ValueError('decompressed disk exceeds the pinned size or time bound')
                    checksum.update(block)
                    stream.write(block)
            if total != size or checksum.hexdigest() != expected:
                raise ValueError('decompressed raw disk identity differs from the pinned input')
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), 0o644)
        publish(temporary, disk)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument('--archive', type=Path, help='official .raw.xz archive downloaded by the user')
    inputs.add_argument('--disk', type=Path, help='already decompressed official raw disk')
    parser.add_argument('--work', type=Path, help='persistent local cache and build directory')
    parser.add_argument('--output', type=Path, help='new output .erofs image')
    parser.add_argument('--gpu-compat', type=Path, help='reuse a verified guest GPU artifact instead of compiling it')
    options = parser.parse_args()
    specification = json.loads((DIRECTORY / 'sources.json').read_text())
    if options.archive is None and options.disk is None:
        print('Download the official input in your browser:')
        print(specification['archive']['url'])
        print('Archive SHA-256: ' + specification['archive']['sha256'])
        print('Then run this script on Linux with --archive FILE --work DIR --output IMAGE.erofs.')
        return
    if options.work is None or options.output is None:
        parser.error('--work and --output are required when an input is supplied')
    if platform.system() != 'Linux' or os.geteuid() != 0:
        parser.error('run with sudo on Linux; macOS requires a Linux VM')
    output = options.output.resolve()
    receipt = output.with_suffix(output.suffix + '.json')
    catalog = output.with_suffix(output.suffix + '.import.json')
    if output.suffix != '.erofs' or any(path.exists() for path in (output, receipt, catalog)):
        parser.error('choose a new .erofs output with no existing image, receipt or import descriptor')
    work = options.work.resolve()
    gpu = options.gpu_compat.resolve() if options.gpu_compat else work / 'gpu-compat'
    build_gpu = options.gpu_compat is None and not (gpu / 'receipt.json').exists()
    required = ['mount', 'umount', 'mkfs.erofs', 'fsck.erofs']
    if build_gpu:
        if platform.machine() != 'aarch64' or platform.libc_ver() != ('glibc', '2.39'):
            parser.error('GPU compilation requires Ubuntu 24.04 arm64; on x86-64 or other Linux hosts, '
                         'provide --gpu-compat or cache the verified artifact under WORK/gpu-compat')
        required += ['cmake', 'ninja', 'c++']
    missing = [tool for tool in required if shutil.which(tool) is None]
    if missing:
        parser.error('missing tools: ' + ', '.join(missing)
                     + '; on Ubuntu install build-essential cmake ninja-build erofs-utils')
    work.mkdir(parents=True, exist_ok=True)
    with (work / '.package.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('another packaging process is using this work directory')
        source = specification['archive']
        cache = work / 'input'
        cache.mkdir(exist_ok=True)
        disk = options.disk.resolve() if options.disk else cache / Path(urlparse(source['url']).path).stem
        archive = options.archive.resolve() if options.archive else None
        if archive is not None and (not archive.is_file() or digest(archive) != source['sha256']):
            raise ValueError('archive SHA-256 differs from the pinned official input')
        if options.disk and not disk.is_file():
            raise ValueError('the supplied raw disk does not exist')
        needed = (0 if disk.exists() else specification['disk']['size']) + (8 << 30)
        if shutil.disk_usage(work).free < needed:
            raise ValueError('insufficient work storage; allow raw-disk size plus 8 GiB for a first run')
        sys.path.insert(0, str(DIRECTORY / 'gpu-compat'))
        from artifact import read_artifact
        if not build_gpu:
            read_artifact(gpu)
        else:
            print('Building the guest GPU compatibility library', flush=True)
            subprocess.run([sys.executable, '-B', str(DIRECTORY / 'gpu-compat/build.py'),
                            '--output', str(gpu)], check=True, timeout=300)
            read_artifact(gpu)
        print('Verifying the official raw disk', flush=True)
        decompress(archive, disk, specification['disk']['size'], specification['disk']['sha256'])
        # derive.py owns mount cleanup and its bounded mkfs/fsck subprocesses.
        # Keep that cleanup in this process instead of timing out a parent
        # subprocess while its disposable mounts are still active.
        import derive
        previous = sys.argv
        try:
            sys.argv = [str(DIRECTORY / 'derive.py'), '--disk', str(disk), '--gpu-compat', str(gpu),
                        '--output', str(output), '--work-root', str(work / 'mounts')]
            derive.main()
        finally:
            sys.argv = previous
        subprocess.run([sys.executable, '-B', str(DIRECTORY / 'accept-image.py'),
                        '--image', str(output), '--receipt', str(receipt), '--catalog', str(catalog)],
                       check=True, timeout=180)
        print('Image: ' + str(output), flush=True)
        print('Producer receipt: ' + str(receipt), flush=True)
        print('Import descriptor: ' + str(catalog), flush=True)
        print('The current app accepts its bundled descriptor only. A locally generated image is not'
              ' automatically accepted; it needs matching app import support or an app build using'
              ' this import descriptor.', flush=True)


if __name__ == '__main__':
    main()
