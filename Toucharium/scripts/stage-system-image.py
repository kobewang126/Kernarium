#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Keep the Toucharium 2 application separate from its imported system image."""
import os
from pathlib import Path

output = Path(os.environ['TARGET_BUILD_DIR']) / os.environ['UNLOCALIZED_RESOURCES_FOLDER_PATH'] / 'UbuntuTouch.erofs'
output.unlink(missing_ok=True)
if os.environ.get('TOUCHARIUM_BUNDLED_IMAGE'):
    raise SystemExit('Toucharium 2 uses imported images; remove TOUCHARIUM_BUNDLED_IMAGE')
