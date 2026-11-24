# SPDX-License-Identifier: GPL-2.0-or-later
"""Verify a guest GPU compatibility artifact against its owning sources."""
from pathlib import Path
import hashlib
import json
import sys

sys.path.insert(0, str(Path(__file__).parent))
from build import source_inputs


def read_artifact(directory: Path) -> bytes:
    receipt = json.loads((directory / 'receipt.json').read_text())
    if (receipt.get('schema_version') != 1 or receipt.get('architecture') != 'aarch64'
            or receipt.get('inputs') != source_inputs()):
        raise ValueError('GPU compatibility artifact source identity does not match')
    data = (directory / 'lib/libtoucharium-mir-gpu.so').read_bytes()
    if hashlib.sha256(data).hexdigest() != receipt.get('library_sha256'):
        raise ValueError('GPU compatibility library digest does not match')
    if (data[:6] != b'\x7fELF\x02\x01' or len(data) < 20
            or int.from_bytes(data[18:20], 'little') != 183):
        raise ValueError('GPU compatibility library is not little-endian ELF64 AArch64')
    return data
