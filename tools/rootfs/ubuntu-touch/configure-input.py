#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Map the Kernarium touchscreen onto the system compositor's display wall."""
from __future__ import annotations

import argparse
import ctypes as C
from pathlib import Path
import pwd
import signal
import sys
import time


def configure(socket: Path, deadline: float) -> None:
    while not socket.exists():
        if time.monotonic() >= deadline:
            raise RuntimeError("system compositor socket did not appear")
        time.sleep(0.1)

    mir = C.CDLL("libmirclient.so.9")
    pointer, string = C.c_void_p, C.c_char_p
    error_callback = C.CFUNCTYPE(None, pointer, pointer, pointer)
    declarations = {
        "mir_connect_sync": (pointer, [string, string]),
        "mir_connection_is_valid": (C.c_bool, [pointer]),
        "mir_connection_get_error_message": (string, [pointer]),
        "mir_connection_release": (None, [pointer]),
        "mir_connection_create_input_config": (pointer, [pointer]),
        "mir_input_config_release": (None, [pointer]),
        "mir_input_config_device_count": (C.c_size_t, [pointer]),
        "mir_input_config_get_mutable_device": (pointer, [pointer, C.c_size_t]),
        "mir_input_device_get_name": (string, [pointer]),
        "mir_input_device_get_mutable_touchscreen_config": (pointer, [pointer]),
        "mir_touchscreen_config_get_mapping_mode": (C.c_int, [pointer]),
        "mir_touchscreen_config_set_mapping_mode": (None, [pointer, C.c_int]),
        "mir_connection_set_base_input_config": (None, [pointer, pointer]),
        "mir_connection_set_error_callback": (None, [pointer, error_callback, pointer]),
        "mir_error_get_domain": (C.c_int, [pointer]),
        "mir_error_get_code": (C.c_uint32, [pointer]),
    }
    for name, (result, arguments) in declarations.items():
        function = getattr(mir, name)
        function.restype = result
        function.argtypes = arguments

    errors: list[tuple[int, int]] = []

    @error_callback
    def failed(_connection, error, _context):
        errors.append((mir.mir_error_get_domain(error), mir.mir_error_get_code(error)))

    connection = mir.mir_connect_sync(str(socket).encode(), b"toucharium-input")
    if not connection:
        raise RuntimeError("cannot create Mir connection")
    try:
        if not mir.mir_connection_is_valid(connection):
            raise RuntimeError(mir.mir_connection_get_error_message(connection).decode())
        mir.mir_connection_set_error_callback(connection, failed, None)
        requested = False
        matched = False
        while time.monotonic() < deadline:
            if errors:
                raise RuntimeError(f"Mir rejected input configuration: {errors}")
            configuration = mir.mir_connection_create_input_config(connection)
            if not configuration:
                raise RuntimeError("cannot read Mir input configuration")
            try:
                found = False
                changed = False
                for index in range(mir.mir_input_config_device_count(configuration)):
                    device = mir.mir_input_config_get_mutable_device(configuration, index)
                    if mir.mir_input_device_get_name(device) != b"Kernarium Touchscreen":
                        continue
                    touchscreen = mir.mir_input_device_get_mutable_touchscreen_config(device)
                    if not touchscreen:
                        raise RuntimeError("virtual touchscreen has no touchscreen configuration")
                    found = True
                    if not matched:
                        print("toucharium-input: virtual touchscreen detected", flush=True)
                        matched = True
                    # Mir's default to-output mapping uses output ID zero,
                    # which is not the virtual KMS connector. Display-wall
                    # mapping follows the active display and its geometry.
                    if mir.mir_touchscreen_config_get_mapping_mode(touchscreen) != 1:
                        mir.mir_touchscreen_config_set_mapping_mode(touchscreen, 1)
                        changed = True
                if found and not changed:
                    print("toucharium-input: mapping acknowledged by compositor", flush=True)
                    break
                if changed and not requested:
                    mir.mir_connection_set_base_input_config(connection, configuration)
                    requested = True
            finally:
                mir.mir_input_config_release(configuration)
            time.sleep(0.1)
        else:
            if not matched:
                raise RuntimeError("virtual touchscreen did not appear")
            raise RuntimeError("virtual touchscreen mapping was not acknowledged")
    finally:
        mir.mir_connection_release(connection)
    print(f"toucharium-input: virtual touchscreen mapped at {socket}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", type=Path)
    options = parser.parse_args()
    # Both Mir servers own a mapping: fixing the system compositor alone
    # leaves Lomiri's nested server pointing at its nonexistent output zero.
    sockets = [options.socket] if options.socket else [
        Path("/run/mir_socket"),
        Path("/run/user") / str(pwd.getpwnam("phablet").pw_uid) / "mir_socket_trusted",
    ]
    # Synchronous Mir connect and disconnect have no timeout argument.
    # Both servers share one deadline bounded by the service's start timeout.
    signal.alarm(135)
    deadline = time.monotonic() + 120
    try:
        for socket in sockets:
            configure(socket, deadline)
    except (OSError, RuntimeError) as error:
        print(f"toucharium-input: {error}", file=sys.stderr)
        return 1
    finally:
        signal.alarm(0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
