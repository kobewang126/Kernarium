#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Embed a verified GPU artifact in the offline packaging script."""
import argparse
import base64
import json
from pathlib import Path
import pprint
import zlib

from artifact import read_artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact', type=Path, required=True)
    parser.add_argument('--script', type=Path, default=Path(__file__).resolve().parent.parent / 'package.py')
    parser.add_argument('--check', action='store_true')
    options = parser.parse_args()
    data = read_artifact(options.artifact)
    receipt = json.loads((options.artifact / 'receipt.json').read_text())
    encoded = base64.b85encode(zlib.compress(data, 9)).decode('ascii')
    begin, end = '# BEGIN GENERATED GPU PAYLOAD', '# END GENERATED GPU PAYLOAD'
    generated = begin + '\nEMBEDDED_GPU_RECEIPT = ' + pprint.pformat(receipt, sort_dicts=True) + '\n'
    generated += 'EMBEDDED_GPU_DATA = (\n'
    generated += ''.join('    b"' + encoded[index:index + 80] + '"\n' for index in range(0, len(encoded), 80))
    generated += ')\n' + end
    source = options.script.read_text()
    if source.count(begin) != 1 or source.count(end) != 1:
        raise ValueError('GPU payload markers are not unique')
    start, stop = source.index(begin), source.index(end) + len(end)
    replacement = source[:start] + generated + source[stop:]
    if options.check:
        if source != replacement:
            raise ValueError('embedded GPU payload differs from the verified artifact')
    else:
        options.script.write_text(replacement)


if __name__ == '__main__':
    main()
