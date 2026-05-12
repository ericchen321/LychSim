"""``lychsim logs <handle>`` -- view or tail a launched UE instance's log."""

from __future__ import annotations

import argparse
import shutil
import sys

from ..log_viewer import iter_appended_chunks, tail_lines
from ..runs_registry import LOG_FILE_NAME, get_runs_dir


HELP = "Print or follow a launched UE instance's redirected log."

LONG_DESCRIPTION = """\
Reads $LYCHSIM_HOME/runs/<handle>/ue.log. Use `lychsim ps` to list active
handles. Old run directories are reaped on every `ps` / `run` invocation,
so you can only tail a handle that's still tracked.

By default prints the last 50 lines. Pass --all for the full log, -n N
for a different count, or -n 0 to skip the history phase entirely (useful
with -f to stream from "now").
"""


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.description = LONG_DESCRIPTION
    parser.formatter_class = argparse.RawDescriptionHelpFormatter
    parser.add_argument("handle", help="Run handle (see `lychsim ps`).")

    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("-n", "--lines", type=int, default=50,
                     help="Show last N lines (default 50, 0 to skip history).")
    grp.add_argument("--all", action="store_true",
                     help="Print the entire log instead of last N.")

    parser.add_argument("-f", "--follow", action="store_true",
                        help="After history, keep printing new content as it arrives.")


def run(args: argparse.Namespace) -> int:
    runs = get_runs_dir()
    run_dir = runs / args.handle
    if not run_dir.is_dir():
        print(f"lychsim: no such handle: {args.handle}", file=sys.stderr)
        return 2

    log_path = run_dir / LOG_FILE_NAME
    if not log_path.exists():
        print(f"lychsim: log file missing: {log_path}", file=sys.stderr)
        return 2

    # Phase 1: history
    if args.all:
        with log_path.open("rb") as f:
            shutil.copyfileobj(f, sys.stdout.buffer)
    elif args.lines > 0:
        sys.stdout.buffer.write(tail_lines(log_path, args.lines))
    sys.stdout.buffer.flush()

    # Snapshot the file end *after* history printing so the follow phase
    # picks up only genuinely-new bytes. A tiny race window remains where
    # bytes appended between tail_lines's read and this stat call can be
    # missed; in practice that's microseconds and a few bytes at worst.
    try:
        history_end = log_path.stat().st_size
    except OSError as e:
        print(f"lychsim: could not stat log file: {e}", file=sys.stderr)
        return 2

    # Footer to stderr so a piped `lychsim logs handle | grep ...` doesn't
    # see our diagnostic line.
    suffix = " (following; Ctrl-C to stop)" if args.follow else ""
    print(f"[lychsim] log: {log_path}{suffix}", file=sys.stderr)

    if not args.follow:
        return 0

    try:
        for chunk in iter_appended_chunks(log_path, history_end):
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
    except KeyboardInterrupt:
        print(file=sys.stderr)  # cleanup newline after ^C
        return 130
    return 0
