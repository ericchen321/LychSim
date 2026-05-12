"""Launching a packaged UE binary in the background.

Mode A only (packaged runtime). Mode B (project mode) is post-v1.

The plugin accepts ``-UnrealCVPort=N`` so we never write to ``unrealcv.ini``;
launches are lock-free across concurrent invocations.
"""

from __future__ import annotations

import configparser
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


# Windows process creation flags (don't import via ctypes; just the constants).
_WIN_DETACHED_PROCESS = 0x00000008
_WIN_CREATE_NEW_PROCESS_GROUP = 0x00000200


def read_default_port(binary: Path) -> int:
    """Best-effort read of the binary's neighbouring ``unrealcv.ini`` port.

    Returns 9000 on any parse error or missing file -- the value is just a
    starting hint for :func:`probe_free_port`.
    """
    ini = binary.parent / "unrealcv.ini"
    if not ini.exists():
        return 9000
    cp = configparser.ConfigParser(strict=False, interpolation=None)
    try:
        cp.read(ini, encoding="utf-8-sig")
    except (configparser.Error, OSError):
        return 9000
    section = "UnrealCV.UnrealCVServer"
    if cp.has_section(section) and cp.has_option(section, "Port"):
        try:
            return cp.getint(section, "Port")
        except ValueError:
            return 9000
    return 9000


def probe_free_port(start: int, max_tries: int = 50, host: str = "127.0.0.1") -> int:
    """Find a free TCP port at or above ``start``."""
    for port in range(start, start + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"no free port in range {start}-{start + max_tries - 1}")


def wait_ready(port: int, timeout: float = 60.0, host: str = "127.0.0.1") -> Optional[float]:
    """Poll ``host:port`` until a TCP connect succeeds.

    Returns the elapsed seconds on success, or ``None`` on timeout.
    """
    deadline = time.monotonic() + timeout
    started = time.monotonic()
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return time.monotonic() - started
        except OSError:
            time.sleep(1.0)
    return None


def spawn_detached(
    cmd: list,
    log_path: Path,
    show_window: bool = True,
) -> int:
    """Spawn a detached UE process; return its pid.

    stdio is redirected to ``log_path`` (``stdin=DEVNULL``, ``stderr`` merged
    into ``stdout``). The CLI process can exit afterwards and UE keeps running.
    """
    log_f = open(log_path, "wb")
    kwargs = dict(
        stdin=subprocess.DEVNULL,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        close_fds=True,
    )
    if sys.platform.startswith("win"):
        flags = _WIN_DETACHED_PROCESS | _WIN_CREATE_NEW_PROCESS_GROUP
        kwargs["creationflags"] = flags
    else:
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(cmd, **kwargs)
    finally:
        log_f.close()
    return proc.pid
