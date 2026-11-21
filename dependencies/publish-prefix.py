#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Publish a staged directory with an exclusive atomic rename or exchange.

Without --swap the rename is exclusive (RENAME_EXCL): creating DESTINATION
and moving SOURCE there are one operation, so it never replaces, or moves
below, a DESTINATION another process published first. With --swap
(RENAME_SWAP) both paths must exist and exchange places.

Exit status: 0 when the rename happened, 1 when an exclusive rename found
DESTINATION already present, and 2 for any other failure.
"""

from __future__ import annotations

__import__("sys").dont_write_bytecode = True

import ctypes
import errno
import os
from pathlib import Path
import sys


RENAME_SWAP = 0x00000002
RENAME_EXCL = 0x00000004
USAGE = "usage: publish-prefix.py [--swap] SOURCE DESTINATION"


def main(argv: list[str]) -> int:
    arguments = argv[1:]
    flags = RENAME_EXCL
    if arguments[:1] == ["--swap"]:
        flags = RENAME_SWAP
        arguments = arguments[1:]
    if len(arguments) != 2:
        print(USAGE, file=sys.stderr)
        return 2

    source = Path(arguments[0])
    destination = Path(arguments[1])
    if not source.is_dir() or source.is_symlink():
        print(f"invalid staged directory: {source}", file=sys.stderr)
        return 2

    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        rename = libc.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        arguments = (os.fsencode(source), os.fsencode(destination), flags)
    elif sys.platform.startswith("linux"):
        # Linux gives the same guarantees with RENAME_NOREPLACE (1) and
        # RENAME_EXCHANGE (2). AT_FDCWD keeps relative paths relative to the
        # caller, exactly as renamex_np does on Darwin.
        rename = libc.renameat2
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p,
                           ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        arguments = (-100, os.fsencode(source), -100, os.fsencode(destination),
                     2 if flags == RENAME_SWAP else 1)
    else:
        print(f"atomic directory publication is unsupported on {sys.platform}",
              file=sys.stderr)
        return 2
    rename.restype = ctypes.c_int
    if rename(*arguments) == 0:
        return 0

    error = ctypes.get_errno()
    if flags == RENAME_EXCL and error == errno.EEXIST:
        return 1
    mode = "swap" if flags == RENAME_SWAP else "exclusive"
    print(
        f"{mode} rename of {source} to {destination} failed: {os.strerror(error)}",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
