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

from setup import install_display_policy, write
from display_policy import render_shell

ORIENTED_SHELL_SHA256 = '36e8a14c5ad1495bfbd4c435260647ef529d87a9d178037fb1cd7cc2ea5431bd'


def render_mode(source: bytes, shell_mode: str) -> bytes:
    if hashlib.sha256(source).hexdigest() != ORIENTED_SHELL_SHA256:
        raise ValueError('OrientedShell digest does not match the pinned PDK')
    usage = {'phone': 'Staged', 'desktop': 'Windowed'}[shell_mode]
    text = source.decode()
    anchor = '    function calculateUsageMode() {'
    if text.count(anchor) != 1:
        raise ValueError('usage mode function is not unique')
    start = text.index(anchor)
    end = text.index('\n    }\n', start) + len('\n    }\n')
    replacement = (anchor + '\n'
                   '        // Toucharium supplies an explicit user choice at boot.\n'
                   '        // Touch-only devices must retain the selected window mode.\n'
                   '        if (lomiriSettings.usageMode === undefined) return;\n'
                   f'        lomiriSettings.usageMode = "{usage}";\n'
                   '        miceModel.oldCount = miceModel.count;\n'
                   '        touchPadModel.oldCount = touchPadModel.count;\n'
                   '    }\n')
    return (text[:start] + replacement + text[end:]).encode()


def install_selection(root: Path, grid_unit: int, shell_mode: str) -> None:
    if shell_mode == 'phone':
        install_display_policy(root, grid_unit)
        return
    if shell_mode != 'desktop' or not 8 <= grid_unit <= 64:
        raise ValueError('unsupported desktop display selection')
    ratio = grid_unit / 8
    write(root, 'etc/deviceinfo/default.yaml',
          '# SPDX-License-Identifier: GPL-2.0-or-later\n'
          'defaults:\n  default:\n    Name: toucharium\n    PrettyName: Toucharium\n'
          f'    DeviceType: desktop\n    GridUnit: {grid_unit}\n    WebkitDpr: {ratio:g}\n')
    write(root, 'etc/ubuntu-touch-session.d/android.conf',
          '# SPDX-License-Identifier: GPL-2.0-or-later\n'
          f'GRID_UNIT_PX={grid_unit}\nQT_AUTO_SCREEN_SCALE_FACTOR=1\nQTWEBKIT_DPR={ratio:g}\n'
          'FORM_FACTOR=desktop\n')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--initramfs", type=Path, required=True)
    parser.add_argument("--lomiri-shell", type=Path, required=True)
    parser.add_argument("--lomiri-oriented-shell", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--shell-mode", choices=('phone', 'desktop'), default='phone')
    options = parser.parse_args()
    pin = json.loads((Path(__file__).parent / "sources.json").read_text())["lomiri_shell"]
    source = options.lomiri_shell.read_bytes()
    if hashlib.sha256(source).hexdigest() != pin["sha256"]:
        raise ValueError("Lomiri Shell digest does not match sources.json")
    oriented = render_mode(options.lomiri_oriented_shell.read_bytes(), options.shell_mode)
    options.output_directory.mkdir(parents=True, exist_ok=True)
    # GuestDisplayScale supports up to eight pixels per point. Integer grid
    # units also cover fractional native scales without duplicating plugins.
    with tempfile.TemporaryDirectory(prefix="toucharium-display-") as temporary:
        root = Path(temporary) / "payload"
        root.mkdir()
        write(root, 'usr/share/lomiri/OrientedShell.qml', oriented.decode())
        for grid_unit in range(8, 65):
            install_selection(root, grid_unit, options.shell_mode)
            # QtMir can report native scale 1 for the virtual connector and
            # replace GRID_UNIT_PX. Correct only the shell's Units object;
            # Qt's global scale also changes Mir's window coordinates.
            target = root / pin["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(render_shell(source, grid_unit))
            target.chmod(0o644)
            prefix = 'TouchariumDesktop' if options.shell_mode == 'desktop' else 'Toucharium'
            output = options.output_directory / f"{prefix}Display{grid_unit}.cpio"
            generated = Path(temporary) / "display.cpio"
            command = [str(options.initramfs.resolve()), "--output=" + str(generated)]
            command += ["--file=/payload/" + str(path.relative_to(root)) + "=" + str(path)
                        for path in sorted(root.rglob("*")) if path.is_file()]
            subprocess.run(command, check=True, timeout=15)
            generated.chmod(0o644)
            generated.replace(output)


if __name__ == "__main__":
    main()
