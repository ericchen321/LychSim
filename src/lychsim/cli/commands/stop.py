"""``lychsim stop`` -- terminate one or all running LychSim instances."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import List, Tuple

import psutil

from ..runs_registry import get_runs_dir, is_alive, iter_live_records, load_record


HELP = "Terminate a running instance by handle, or 'all' (with confirmation)."


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("target", help="Handle name (e.g. 'newyorkstreet-1'), or 'all'.")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="Skip the confirmation prompt for 'stop all'.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be stopped without acting.")
    parser.add_argument("--grace", type=float, default=5.0,
                        help="Seconds to wait after terminate() before kill() (default 5).")


def _terminate(rec: dict, grace: float) -> str:
    """Terminate one process. Returns 'terminated', 'killed', 'gone', or 'error: ...'."""
    pid = rec.get("pid")
    if not isinstance(pid, int) or pid <= 0 or not psutil.pid_exists(pid):
        return "gone"
    try:
        proc = psutil.Process(pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        return f"error: {e}"
    try:
        proc.terminate()
        try:
            proc.wait(timeout=grace)
            return "terminated"
        except psutil.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=grace)
            except psutil.TimeoutExpired:
                pass
            return "killed"
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        return f"error: {e}"


def _purge(run_dir: Path) -> None:
    shutil.rmtree(run_dir, ignore_errors=True)


def _print_target_row(handle: str, rec: dict) -> None:
    pid = rec.get("pid", "?")
    port = rec.get("port", "?")
    env = rec.get("env_name", "?")
    print(f"  {handle}  env={env}  pid={pid}  port={port}")


def _stop_all(args: argparse.Namespace) -> int:
    targets: List[Tuple[str, dict]] = list(iter_live_records())
    if not targets:
        print("[lychsim] no running instances.")
        return 0

    if args.dry_run:
        print(f"[lychsim] would stop {len(targets)} instance(s):")
        for h, rec in targets:
            _print_target_row(h, rec)
        return 0

    if not args.yes:
        print(f"[lychsim] about to terminate {len(targets)} instance(s):")
        for h, rec in targets:
            _print_target_row(h, rec)
        try:
            ans = input("Proceed? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            ans = ""
        if ans not in ("y", "yes"):
            print("[lychsim] aborted.")
            return 1

    runs_dir = get_runs_dir()
    rc = 0
    for h, rec in targets:
        outcome = _terminate(rec, args.grace)
        _purge(runs_dir / h)
        print(f"[lychsim] {h}: {outcome}")
        if outcome.startswith("error"):
            rc = 1
    return rc


def _stop_one(args: argparse.Namespace) -> int:
    runs_dir = get_runs_dir()
    run_dir = runs_dir / args.target
    rec = load_record(run_dir)
    if rec is None:
        print(f"lychsim: no such handle: {args.target}", file=sys.stderr)
        return 2

    alive = is_alive(rec)
    if args.dry_run:
        state = "alive" if alive else "stale"
        print(f"[lychsim] would stop {args.target}  pid={rec.get('pid')} ({state})")
        return 0

    if not alive:
        print(f"[lychsim] {args.target}: already gone (cleaning up registry)")
        _purge(run_dir)
        return 0

    outcome = _terminate(rec, args.grace)
    _purge(run_dir)
    print(f"[lychsim] {args.target}: {outcome}")
    return 0 if not outcome.startswith("error") else 1


def run(args: argparse.Namespace) -> int:
    if args.target.lower() == "all":
        return _stop_all(args)
    return _stop_one(args)
