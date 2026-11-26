#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Verify an external image receipt and publish its application import descriptor."""
import argparse
import json
from pathlib import Path

from derive import digest, source_inputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, required=True)
    options = parser.parse_args()
    record = json.loads(options.receipt.read_text())
    if (record.get('schema_version') != 1 or record.get('policy_version') != 2
            or record.get('policy_sources') != source_inputs()):
        raise ValueError('image receipt does not match current producer inputs')
    if (options.image.name != record['image'] or options.image.stat().st_size != record['size']
            or digest(options.image) != record['sha256']):
        raise ValueError('image size or checksum does not match receipt')
    catalog = {'filename': record['image'], 'size': record['size'],
               'sha256': record['sha256'], 'policyVersion': record['policy_version']}
    options.catalog.write_text(json.dumps(catalog, indent=2) + '\n')


if __name__ == '__main__':
    main()
