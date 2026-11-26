#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Supply AccountsService's regional fallback without replacing a chosen locale."""
from pathlib import Path
import re


def configure(path: Path) -> None:
    text = path.read_text() if path.exists() else ''
    for line in text.splitlines():
        match = re.fullmatch(r'\s*LANG\s*=\s*(.*?)\s*', line)
        if match and match[1].strip('"\''):
            return
    # Write through an existing bind mount instead of replacing its inode.
    with path.open('a') as stream:
        stream.write(('\n' if text and not text.endswith('\n') else '') + 'LANG=C.UTF-8\n')


if __name__ == '__main__':
    configure(Path('/etc/default/locale'))
