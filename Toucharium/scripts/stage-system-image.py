#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Optionally embed the pinned Ubuntu Touch base without copying it at launch."""
import hashlib
import os
from pathlib import Path
import shutil

output = Path(os.environ['TARGET_BUILD_DIR']) / os.environ['UNLOCALIZED_RESOURCES_FOLDER_PATH'] / 'UbuntuTouch.erofs'
source = os.environ.get('TOUCHARIUM_BUNDLED_IMAGE')
if not source:
    output.unlink(missing_ok=True)
else:
    image = Path(source)
    expected = 'eb16c023039e3217040cb1befd8796b025daa60fe216c4140e9f5755b4b9b6e6'
    digest = hashlib.sha256()
    with image.open('rb') as stream:
        while chunk := stream.read(4 << 20):
            digest.update(chunk)
    if image.stat().st_size != 2179211264 or digest.hexdigest() != expected:
        raise SystemExit('Bundled image must be the complete pinned PDK 470 r1 image')
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(image, output)
    output.chmod(0o644)
    print('Embedded verified Ubuntu Touch base image')
