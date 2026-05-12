"""Runs registry: ``$LYCHSIM_HOME/runs/<handle>/run.json``.

Ephemeral state -- one directory per launched UE instance, holding
metadata + the redirected ``ue.log``. Stale entries (pid dead OR exe
mismatch) are reaped by callers via :func:`reap_stale`.
"""

from __future__ import annotations

import itertools
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

import psutil

from .home import ensure_lychsim_home


RUNS_DIR_NAME = "runs"
RUN_FILE_NAME = "run.json"
LOG_FILE_NAME = "ue.log"


def get_runs_dir() -> Path:
    return ensure_lychsim_home() / RUNS_DIR_NAME


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "env"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _norm(p: str) -> str:
    return os.path.normcase(os.path.normpath(p))


def is_alive(record: dict) -> bool:
    """Return True iff the process recorded in ``record`` is the same UE
    instance we launched (pid alive AND exe matches the recorded binary)."""
    pid = record.get("pid")
    binary = record.get("binary") or ""
    if not isinstance(pid, int) or pid <= 0:
        return False
    if not psutil.pid_exists(pid):
        return False
    try:
        proc = psutil.Process(pid)
        exe = proc.exe()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False
    if not exe or not binary:
        return False
    return _norm(exe) == _norm(binary)


def load_record(run_dir: Path) -> Optional[dict]:
    rec_path = run_dir / RUN_FILE_NAME
    if not rec_path.exists():
        return None
    try:
        return json.loads(rec_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save_record(run_dir: Path, record: dict) -> Path:
    """Write ``run.json`` atomically inside ``run_dir`` (assumed to exist)."""
    target = run_dir / RUN_FILE_NAME
    tmp = run_dir / (RUN_FILE_NAME + ".tmp")
    tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, target)
    return target


def reap_stale(runs_dir: Optional[Path] = None) -> list:
    """Delete every stale run directory; return their handle names."""
    if runs_dir is None:
        runs_dir = get_runs_dir()
    if not runs_dir.exists():
        return []
    reaped = []
    for d in sorted(runs_dir.iterdir()):
        if not d.is_dir():
            continue
        rec = load_record(d)
        if rec is None or not is_alive(rec):
            shutil.rmtree(d, ignore_errors=True)
            reaped.append(d.name)
    return reaped


def iter_live_records(runs_dir: Optional[Path] = None):
    """Yield ``(handle, record)`` for every still-alive run."""
    if runs_dir is None:
        runs_dir = get_runs_dir()
    if not runs_dir.exists():
        return
    for d in sorted(runs_dir.iterdir()):
        if not d.is_dir():
            continue
        rec = load_record(d)
        if rec is None or not is_alive(rec):
            continue
        yield d.name, rec


def allocate_handle(env_name: str, runs_dir: Optional[Path] = None) -> Tuple[str, Path]:
    """Atomically allocate a new ``<slug>-<n>`` handle dir.

    Reaps stale dirs first so ``n`` doesn't drift forever. Race-safe via
    ``mkdir(exist_ok=False)``.
    """
    if runs_dir is None:
        runs_dir = get_runs_dir()
    runs_dir.mkdir(parents=True, exist_ok=True)
    reap_stale(runs_dir)
    slug = _slug(env_name)
    for n in itertools.count(1):
        handle = f"{slug}-{n}"
        d = runs_dir / handle
        try:
            d.mkdir(parents=False, exist_ok=False)
            return handle, d
        except FileExistsError:
            continue
    raise RuntimeError("unreachable")  # pragma: no cover
