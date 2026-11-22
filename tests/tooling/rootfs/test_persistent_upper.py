#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise the init's persistent-upper data protection with injected tools."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import tempfile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--init", type=Path, required=True)
    args = parser.parse_args()
    functions, separator, _ = args.init.read_text().partition("\nread_parameters\nmount ")
    if not separator:
        raise RuntimeError("cannot isolate init functions from PID 1 entry point")
    with tempfile.TemporaryDirectory(prefix="persistent-upper-test-") as name:
        directory = Path(name)
        disk = directory / "disk"
        log = directory / "calls"
        tools = {
            "busybox": 'shift\nexec /bin/dd "$@"\n',
            "blkid": '[ "$TEST_EXT4" = 1 ] || exit 2\necho \'TYPE="ext4"\'\n',
            "e2fsck": 'echo check >> "$TEST_LOG"\nexit "$TEST_CHECK_STATUS"\n',
            "sync": 'echo sync >> "$TEST_LOG"\n',
            # Fail unless the grant has already been consumed. No tool can
            # format a second time merely because the first attempt failed.
            "mkfs.ext4": 'echo format >> "$TEST_LOG"\n'
                'if /usr/bin/cmp -s "$TEST_DISK" "$TEST_GRANT"; then exit 99; fi\n'
                'exit "$TEST_FORMAT_STATUS"\n',
        }
        for tool, body in tools.items():
            path = directory / tool
            path.write_text("#!/bin/sh\n" + body)
            path.chmod(0o755)
        grant = b"UML_BOOT_EMPTY_OVERLAY_V1\n"
        (directory / "grant").write_bytes(grant)

        def run(*, ext4: bool = False, check: int = 0, formatting: int = 0):
            log.write_text("")
            environment = dict(os.environ, TEST_EXT4=str(int(ext4)),
                TEST_CHECK_STATUS=str(check), TEST_FORMAT_STATUS=str(formatting),
                TEST_LOG=str(log), TEST_DISK=str(disk), TEST_GRANT=str(directory / "grant"))
            code = functions + '\nPATH="$TEST_TOOLS:$PATH"\n' + \
                'upper_device="$TEST_DISK"\nprepare_persistent_upper\n'
            environment["TEST_TOOLS"] = str(directory)
            result = subprocess.run(["/bin/sh"], input=code, text=True,
                capture_output=True, env=environment, timeout=10)
            return result, log.read_text().splitlines()

        disk.write_bytes(grant)
        result, calls = run()
        assert result.returncode == 0, result.stdout + result.stderr
        assert calls == ["sync", "format"], calls
        assert disk.read_bytes() == bytes(len(grant))

        for status in (0, 1, 2):
            disk.write_bytes(b"existing user data")
            result, calls = run(ext4=True, check=status)
            assert result.returncode == 0, result.stdout + result.stderr
            assert calls == ["check"] and disk.read_bytes() == b"existing user data"

        result, calls = run(ext4=True, check=4)
        assert result.returncode != 0 and calls == ["check"]
        assert disk.read_bytes() == b"existing user data"
        result, calls = run()
        assert result.returncode != 0 and not calls
        assert disk.read_bytes() == b"existing user data"

        disk.write_bytes(grant)
        result, calls = run(formatting=1)
        assert result.returncode != 0 and calls == ["sync", "format"]
        consumed = disk.read_bytes()
        result, calls = run()
        assert result.returncode != 0 and not calls
        assert disk.read_bytes() == consumed


if __name__ == "__main__":
    main()
