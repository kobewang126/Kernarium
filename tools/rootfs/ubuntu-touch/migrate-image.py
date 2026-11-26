#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Migrate owned boot policy files from a verified lower image before systemd."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import shutil
import tempfile


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class SymlinkPathError(ValueError):
    pass


def resolve(root: Path, name: str) -> Path:
    relative = PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts or not relative.parts:
        raise ValueError('invalid managed policy path')
    path = root
    for part in relative.parts:
        path /= part
        if path.is_symlink():
            raise SymlinkPathError('managed policy path is a symlink: ' + name)
    return path


def sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def publish(path: Path, data: bytes, mode: int) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.toucharium-', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(data)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
            temporary.replace(path)
            sync_directory(path.parent)
        finally:
            temporary.unlink(missing_ok=True)


def migrate(root: Path, lower: Path) -> list[str]:
    raw = resolve(lower, 'usr/lib/toucharium/image-policy.json').read_bytes()
    policy = json.loads(raw)
    if policy['schema_version'] != 1 or policy['policy_version'] != 2:
        raise ValueError('unsupported image policy')
    backup = resolve(root, 'var/lib/toucharium/migrations/' + digest(raw))
    marker = resolve(backup, 'complete.json')
    if marker.exists():
        try:
            preserved = json.loads(marker.read_text())['preserved']
            if isinstance(preserved, list) and all(isinstance(name, str) for name in preserved):
                return preserved
        except (ValueError, KeyError, TypeError):
            # Recover a truncated completion record from an interrupted boot.
            pass
    plan, preserved = [], []
    # Validate every source before changing any live file.
    for name, item in policy['files'].items():
        source = resolve(lower, name)
        data = source.read_bytes()
        if digest(data) != item['sha256']:
            raise ValueError('image policy file checksum differs: ' + name)
        try:
            target = resolve(root, name)
        except SymlinkPathError:
            # Ubuntu's writable-path setup redirects some /etc files after
            # first boot. Preserve these just like unknown custom contents.
            preserved.append(name)
            continue
        if target.exists():
            current = target.read_bytes()
            if digest(current) == item['sha256']:
                continue
            if digest(current) not in item['previous_sha256']:
                preserved.append(name)
                continue
        plan.append((name, target, data, item['mode']))
    backup.mkdir(parents=True, exist_ok=True)
    for name, target, data, mode in plan:
        if target.exists():
            saved = resolve(backup, 'files/' + name)
            saved.parent.mkdir(parents=True, exist_ok=True)
            # Keep the original backup when recovering an interrupted migration.
            if not saved.exists():
                shutil.copy2(target, saved)
                with saved.open('rb') as stream:
                    os.fsync(stream.fileno())
                sync_directory(saved.parent)
        target.parent.mkdir(parents=True, exist_ok=True)
        publish(target, data, mode)
    publish(marker, (json.dumps({'preserved': preserved}) + '\n').encode(), 0o644)
    return preserved


if __name__ == '__main__':
    conflicts = migrate(Path('/'), Path('/.uml-lower'))
    print('Toucharium image policy ready; preserved custom files:', len(conflicts), flush=True)
