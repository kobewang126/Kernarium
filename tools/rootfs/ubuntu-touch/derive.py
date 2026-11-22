#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Derive a Kernarium EROFS guest from the pinned Ubuntu Touch PDK disk.

Runs as root on Linux. The source is mounted read-only, and all policy changes
live in a disposable overlay. The output is never written over an existing
image. The receipt records the source, policy, compressor and output hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from setup import apply

DIRECTORY = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            checksum.update(block)
    return checksum.hexdigest()


def run(arguments: list[str], timeout: int = 90) -> subprocess.CompletedProcess:
    print("+", " ".join(arguments), flush=True)
    return subprocess.run(arguments, check=True, text=True, timeout=timeout)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disk", type=Path, required=True,
                        help="uncompressed official PDK raw disk")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True,
                        help="Linux filesystem supporting overlayfs")
    options = parser.parse_args()
    if os.geteuid() != 0 or os.uname().sysname != "Linux":
        parser.error("this derivation requires root on Linux")
    source = options.disk.resolve()
    output = options.output.resolve()
    receipt = output.with_suffix(output.suffix + ".json")
    if output.exists() or receipt.exists():
        parser.error("output image or receipt already exists")
    specification = json.loads((DIRECTORY / "sources.json").read_text())
    disk = specification["disk"]
    if source.stat().st_size != disk["size"] or digest(source) != disk["sha256"]:
        parser.error("PDK disk size or SHA-256 differs from the pinned input")
    with source.open("rb") as handle:
        handle.seek(disk["root_offset"] + 1080)
        if handle.read(2) != b"\x53\xef":
            parser.error("pinned root partition is not ext4")
    for tool in ("mount", "umount", "mkfs.erofs", "fsck.erofs"):
        if not shutil.which(tool):
            parser.error(f"required tool is unavailable: {tool}")
    options.work_root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="toucharium-", dir=options.work_root))
    lower, upper, overlay_work, merged = [work / name for name in
                                         ("lower", "upper", "work", "root")]
    for directory in (lower, upper, overlay_work, merged):
        directory.mkdir()
    mounted_lower = mounted_overlay = False
    stage = work / "rootfs.erofs"
    try:
        run(["mount", "-t", "ext4", "-o",
             f"ro,noload,loop,offset={disk['root_offset']},sizelimit={disk['root_size']}",
             str(source), str(lower)])
        mounted_lower = True
        run(["mount", "-t", "overlay", "overlay", "-o",
             f"lowerdir={lower},upperdir={upper},workdir={overlay_work}", str(merged)])
        mounted_overlay = True
        apply(merged)
        # Older erofs-utils fixes the block size at 4 KiB and has no -b flag.
        # Check the produced superblock before accepting either tool version.
        run(["mkfs.erofs", "--quiet", "-zlz4hc,9", str(stage), str(merged)],
            timeout=1800)
        with stage.open("rb") as image:
            image.seek(1024)
            superblock = image.read(13)
        if superblock[:4] != b"\xe2\xe1\xf5\xe0" or superblock[12:] != b"\x0c":
            raise ValueError("EROFS image must use 4 KiB blocks")
        run(["fsck.erofs", str(stage)], timeout=600)
        record = {
            "schema_version": 1,
            "source_release": specification["release"],
            "source_disk_sha256": disk["sha256"],
            "setup_sha256": digest(DIRECTORY / "setup.py"),
            "input_policy_sha256": digest(DIRECTORY / "configure-input.py"),
            "producer_sha256": digest(Path(__file__)),
            "compressor": "mkfs.erofs lz4hc,9",
            "compressor_sha256": digest(Path(shutil.which("mkfs.erofs"))),
            "image": output.name,
            "size": stage.stat().st_size,
            "sha256": digest(stage),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        # Copy to an exclusively created file: another producer's accepted
        # image must never be replaced, including across filesystems.
        with stage.open("rb") as source_image, output.open("xb") as destination:
            shutil.copyfileobj(source_image, destination, 8 << 20)
        with receipt.open("x") as handle:
            json.dump(record, handle, indent=2)
            handle.write("\n")
        print(f"UBUNTU_TOUCH_IMAGE_READY:{output}", flush=True)
    finally:
        if mounted_overlay:
            run(["umount", str(merged)])
            mounted_overlay = False
        if mounted_lower:
            run(["umount", str(lower)])
            mounted_lower = False
        # Never recursively remove a directory while a guest filesystem is
        # still mounted beneath it. An unmount failure leaves it for diagnosis.
        if not mounted_overlay and not mounted_lower:
            shutil.rmtree(work)


if __name__ == "__main__":
    main()
