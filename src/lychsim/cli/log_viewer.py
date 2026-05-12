"""Helpers for reading log files: tail last N lines, follow appended bytes.

These are pure file utilities -- no argparse, no command knowledge. The
``lychsim logs`` command is a thin wrapper around them.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Iterator


_CHUNK = 8 * 1024


def tail_lines(path: Path, n: int) -> bytes:
    """Return the last ``n`` lines of ``path`` as raw bytes (newlines included).

    Backward-reads the file in 8 KB chunks so a multi-GB log file does not
    fully load into memory. Returns ``b""`` when ``n <= 0`` or the file is
    empty. Returns the whole file if it has fewer than ``n`` lines.

    The returned bytes are deliberately undecoded -- the caller is expected
    to write them straight to ``sys.stdout.buffer`` so the terminal handles
    decoding (and we don't choke on partially-corrupted bytes).
    """
    if n <= 0:
        return b""

    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        end = f.tell()
        if end == 0:
            return b""

        # Walk backwards counting newlines. We aim for n+1 newlines if the
        # file ends with one (so the trailing empty line doesn't count),
        # otherwise n.
        f.seek(end - 1)
        has_trailing = (f.read(1) == b"\n")
        target = n + 1 if has_trailing else n

        newlines = 0
        chunks = []
        pos = end
        while pos > 0 and newlines < target:
            read_size = min(_CHUNK, pos)
            pos -= read_size
            f.seek(pos)
            chunk = f.read(read_size)
            chunks.append(chunk)
            newlines += chunk.count(b"\n")

        chunks.reverse()
        data = b"".join(chunks)

        if newlines < target:
            # File has fewer than n lines total -- return all of it.
            return data

        # Skip past (newlines - target + 1) leading newlines, then return
        # everything after.
        skip = newlines - target + 1
        idx = -1
        for _ in range(skip):
            idx = data.find(b"\n", idx + 1)
        return data[idx + 1:]


def iter_appended_chunks(
    path: Path,
    start_offset: int,
    poll_interval: float = 0.5,
) -> Iterator[bytes]:
    """Yield bytes appended to ``path`` after ``start_offset``.

    Polls ``os.stat().st_size`` every ``poll_interval`` seconds; reads new
    bytes when the file grows. Detects truncation (``st_size < pos`` ->
    reopen at offset 0). Generator -- the caller stops by breaking out of
    the loop, typically on ``KeyboardInterrupt``.
    """
    f = path.open("rb")
    f.seek(start_offset)
    pos = start_offset
    try:
        while True:
            chunk = f.read()
            if chunk:
                yield chunk
                pos = f.tell()
                continue

            # No new data; check size for grow / truncate.
            try:
                size = path.stat().st_size
            except OSError:
                time.sleep(poll_interval)
                continue
            if size < pos:
                # File was truncated. Reopen and start over.
                f.close()
                f = path.open("rb")
                pos = 0
                continue
            if size == pos:
                time.sleep(poll_interval)
                continue
            # Size grew but f.read() returned empty -- some platforms cache
            # EOF state. Force a seek to clear it.
            f.seek(pos)
    finally:
        f.close()
