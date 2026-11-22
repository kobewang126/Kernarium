#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Package display-density overrides for the host's supported display scales."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from setup import install_display_policy


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--initramfs", type=Path, required=True)
    parser.add_argument("--lomiri-shell", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    options = parser.parse_args()
    pin = json.loads((Path(__file__).parent / "sources.json").read_text())["lomiri_shell"]
    source = options.lomiri_shell.read_bytes()
    if hashlib.sha256(source).hexdigest() != pin["sha256"]:
        raise ValueError("Lomiri Shell digest does not match sources.json")
    shell = source.decode()
    anchor = "    id: shell\n"
    if shell.count(anchor) != 1:
        raise ValueError("Lomiri Shell root is not unique")
    options.output_directory.mkdir(parents=True, exist_ok=True)
    # GuestDisplayScale supports up to eight pixels per point. Integer grid
    # units also cover fractional native scales without duplicating plugins.
    with tempfile.TemporaryDirectory(prefix="toucharium-display-") as temporary:
        root = Path(temporary) / "payload"
        root.mkdir()
        for grid_unit in range(8, 65):
            install_display_policy(root, grid_unit)
            # QtMir can report native scale 1 for the virtual connector and
            # replace GRID_UNIT_PX. Correct only the shell's Units object;
            # Qt's global scale also changes Mir's window coordinates.
            override = f'''
    // SPDX-License-Identifier: GPL-3.0-only
    readonly property real touchariumGridUnit: {grid_unit}
    function touchariumApplyGridUnit() {{
        if (units.gridUnit !== touchariumGridUnit)
            units.gridUnit = touchariumGridUnit
    }}
    Connections {{
        target: units
        function onGridUnitChanged() {{ shell.touchariumApplyGridUnit() }}
    }}
    Timer {{
        interval: 1; running: true; repeat: false; triggeredOnStart: true
        onTriggered: shell.touchariumApplyGridUnit()
    }}
'''
            target = root / pin["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(shell.replace(anchor, anchor + override, 1))
            target.chmod(0o644)
            output = options.output_directory / f"TouchariumDisplay{grid_unit}.cpio"
            generated = Path(temporary) / "display.cpio"
            command = [str(options.initramfs.resolve()), "--output=" + str(generated)]
            command += ["--file=/payload/" + str(path.relative_to(root)) + "=" + str(path)
                        for path in sorted(root.rglob("*")) if path.is_file()]
            subprocess.run(command, check=True, timeout=15)
            generated.chmod(0o644)
            generated.replace(output)


if __name__ == "__main__":
    main()
