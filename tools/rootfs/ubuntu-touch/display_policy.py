# SPDX-License-Identifier: GPL-2.0-or-later
"""Render the density override for the pinned Lomiri shell."""
from pathlib import Path
import hashlib
import json


def render_shell(source: bytes, grid_unit: int) -> str:
    directory = Path(__file__).parent
    pin = json.loads((directory / 'sources.json').read_text())['lomiri_shell']
    if hashlib.sha256(source).hexdigest() != pin['sha256']:
        raise ValueError('Lomiri Shell digest does not match sources.json')
    shell = source.decode()
    anchor = '    id: shell\n'
    if shell.count(anchor) != 1:
        raise ValueError('Lomiri Shell root is not unique')
    override = (directory / 'lomiri-grid-unit.qml.in').read_text().replace('@GRID_UNIT@', str(grid_unit))
    return shell.replace(anchor, anchor + override, 1)
