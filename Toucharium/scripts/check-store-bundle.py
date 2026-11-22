#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Validate a Toucharium store candidate without uploading it."""

from __future__ import annotations

import argparse
import importlib.util
import plistlib
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", type=Path)
    parser.add_argument("--archive", action="store_true", help="require a clean source tree and accepted kernels")
    args = parser.parse_args()
    app = args.app
    spec = importlib.util.spec_from_file_location(
        "store_binary_checks", ROOT / "Andarium/scripts/check-app-store-bundle.py")
    checks = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = checks
    spec.loader.exec_module(checks)
    problems = []
    if args.archive:
        status = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain"],
            capture_output=True, text=True, timeout=30, check=True)
        if status.stdout.strip():
            problems.append("archive requires a clean committed source tree")
    try:
        info = plistlib.loads((app / "Info.plist").read_bytes())
    except (OSError, ValueError) as error:
        parser.error(f"cannot read application Info.plist: {error}")
    if info.get("UIDeviceFamily") != [1]:
        problems.append("store configuration must target iPhone only")
    if info.get("ITSAppUsesNonExemptEncryption") is not False:
        problems.append("declare the export-compliance encryption answer")
    if "UIBackgroundModes" in info:
        problems.append("store configuration must not declare audio background execution")
    for key in ("GuestPrivacyPolicyURL", "GuestSupportURL", "GuestSourceURL"):
        value = info.get(key, "")
        parts = urlsplit(value) if isinstance(value, str) else urlsplit("")
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            problems.append(f"{key}: configure a public HTTPS URL in Publication.local.xcconfig")
        elif parts.hostname in ("example.org", "example.com", "example.net"):
            problems.append(f"{key}: replace the example URL")
    binaries = checks.executables(app)
    if not checks.executables_of(app):
        problems.append("application executable is missing")
    for binary in binaries:
        allowed = checks.LINUX_BOOT_PARAMETERS if binary.name == "KRuntime_6_18_4K" else frozenset()
        if binary.parent == app:
            # Persistent-overlay format magic, not a process environment knob.
            allowed = frozenset({"UML_BOOT_EMPTY_OVERLAY_V1"})
        problems.extend(f"{binary.name}: automation knob {name}" for name in checks.knobs(binary, allowed))
        problems.extend(f"{binary.name}: debugging support {name}" for name in checks.debug_support(binary))
        problems.extend(f"{binary.name}: {text}" for text in checks.build_host_traces(
            binary, debug_map=binary.parent != app))
    for path in app.rglob("*"):
        if checks.TEST_SUPPORT.match(path.name):
            problems.append(f"test support is embedded: {path.name}")
    result = subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts/check-privacy-manifests.py"), str(app)],
        timeout=180, check=False)
    if args.archive:
        accepted = subprocess.run(
            [sys.executable, "-B", str(ROOT / "scripts/check-embedded-artifacts.py"),
             "--kernel", "arm64", "--kernel", "android", "--app", str(app)],
            timeout=180, check=False)
        if accepted.returncode:
            problems.append("embedded kernel provenance check failed")
    for problem in problems:
        print(f"Toucharium store check: {problem}", file=sys.stderr)
    if problems or result.returncode:
        return 1
    print("Toucharium store candidate: binary policy, publication URLs and privacy checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
