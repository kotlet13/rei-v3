"""Trusted stdlib-only start gate for the bounded process-tree runner.

The parent starts this file with no requested command in argv or environment,
places it inside the platform containment boundary, captures its stable start
identity, and records the telemetry baseline.  Only then does the parent write
one bounded launch frame to stdin.  A partial, invalid, or missing frame never
launches the requested workload.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


MAX_COMMAND_ARGUMENTS = 256
MAX_COMMAND_UTF8_BYTES = 131_072
MAX_ENVIRONMENT_VARIABLES = 1_024
MAX_ENVIRONMENT_UTF8_BYTES = 262_144
MAX_WORKING_DIRECTORY_UTF8_BYTES = 8_192
MAX_LAUNCH_PAYLOAD_BYTES = 524_288
MAX_HEADER_BYTES = 32


def _utf8_size(value: str) -> int:
    return len(value.encode("utf-8"))


def _read_exact(stream: Any, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise ValueError("truncated payload")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _read_payload() -> dict[str, Any]:
    stream = sys.stdin.buffer
    header = stream.readline(MAX_HEADER_BYTES + 1)
    if not header.endswith(b"\n") or len(header) > MAX_HEADER_BYTES:
        raise ValueError("invalid payload header")
    size_text = header[:-1]
    if not size_text.isdigit():
        raise ValueError("invalid payload size")
    size = int(size_text)
    if not 1 <= size <= MAX_LAUNCH_PAYLOAD_BYTES:
        raise ValueError("payload outside fixed bound")
    payload = _read_exact(stream, size)
    if stream.read(1) != b"":
        raise ValueError("trailing payload bytes")
    decoded = json.loads(payload.decode("utf-8"))
    if not isinstance(decoded, dict) or set(decoded) != {
        "command",
        "deadline_monotonic_ns",
        "environment",
        "working_directory",
    }:
        raise ValueError("invalid payload object")
    return decoded


def _validate_payload(
    payload: dict[str, Any],
) -> tuple[tuple[str, ...], dict[str, str], str, int]:
    command_value = payload["command"]
    deadline_monotonic_ns = payload["deadline_monotonic_ns"]
    environment_value = payload["environment"]
    working_directory = payload["working_directory"]
    if (
        not isinstance(command_value, list)
        or not 1 <= len(command_value) <= MAX_COMMAND_ARGUMENTS
        or not all(isinstance(item, str) and item for item in command_value)
    ):
        raise ValueError("invalid command")
    command = tuple(command_value)
    if not Path(command[0]).is_absolute() or any("\x00" in item for item in command):
        raise ValueError("invalid command path")
    if sum(_utf8_size(item) + 1 for item in command) > MAX_COMMAND_UTF8_BYTES:
        raise ValueError("command outside fixed bound")

    if (
        not isinstance(environment_value, dict)
        or len(environment_value) > MAX_ENVIRONMENT_VARIABLES
    ):
        raise ValueError("invalid environment")
    environment: dict[str, str] = {}
    environment_size = 0
    for key, value in environment_value.items():
        if (
            not isinstance(key, str)
            or not key
            or "=" in key
            or "\x00" in key
            or not isinstance(value, str)
            or "\x00" in value
        ):
            raise ValueError("invalid environment entry")
        environment[key] = value
        environment_size += _utf8_size(key) + _utf8_size(value) + 2
    if environment_size > MAX_ENVIRONMENT_UTF8_BYTES:
        raise ValueError("environment outside fixed bound")

    if (
        not isinstance(working_directory, str)
        or not Path(working_directory).is_absolute()
        or "\x00" in working_directory
        or _utf8_size(working_directory) > MAX_WORKING_DIRECTORY_UTF8_BYTES
    ):
        raise ValueError("invalid working directory")
    if (
        type(deadline_monotonic_ns) is not int
        or not 0 < deadline_monotonic_ns <= 0x7FFFFFFFFFFFFFFF
    ):
        raise ValueError("invalid monotonic deadline")
    return command, environment, working_directory, deadline_monotonic_ns


def main() -> int:
    try:
        command, environment, working_directory, deadline_monotonic_ns = (
            _validate_payload(_read_payload())
        )
    except Exception:
        return 120
    try:
        if time.monotonic_ns() >= deadline_monotonic_ns:
            return 123
        process = subprocess.Popen(
            list(command),
            cwd=working_directory,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=None,
            stderr=None,
            shell=False,
            close_fds=True,
        )
        return_code = process.wait()
    except Exception:
        return 121
    return return_code if 0 <= return_code <= 0xFFFFFFFF else 122


if __name__ == "__main__":
    raise SystemExit(main())
