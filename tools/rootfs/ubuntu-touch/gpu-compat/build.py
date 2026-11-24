#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build the pinned guest Mesa compatibility library on Ubuntu 24.04 arm64."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import subprocess


def source_inputs():
    root = Path(__file__).resolve().parent
    paths = [root / name for name in ('gpu_compat.cpp', 'CMakeLists.txt', 'build.py')]
    paths.append(root.parent / 'sources.json')
    return {str(p.relative_to(root.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    options = parser.parse_args()
    if platform.system() != 'Linux' or platform.machine() != 'aarch64':
        parser.error('build on arm64 Linux')
    if platform.libc_ver() != ('glibc', '2.39'):
        parser.error('the pinned guest requires the Ubuntu 24.04 glibc 2.39 toolchain')
    output = options.output.resolve()
    if (output / 'receipt.json').exists():
        parser.error('output already contains an artifact; select a new output directory')
    source = Path(__file__).resolve().parent
    subprocess.run(['cmake', '-S', str(source), '-B', str(output / 'build'), '-G', 'Ninja',
                    '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_INSTALL_PREFIX=' + str(output)],
                   check=True, timeout=60)
    subprocess.run(['cmake', '--build', str(output / 'build'), '--target', 'install', '-j2'],
                   check=True, timeout=180)
    library = output / 'lib/libtoucharium-mir-gpu.so'
    receipt = {'schema_version': 1, 'architecture': 'aarch64',
               'inputs': source_inputs(),
               'library_sha256': hashlib.sha256(library.read_bytes()).hexdigest()}
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
