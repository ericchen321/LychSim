"""Persistent registry of UE envs registered via ``lychsim env add``.

Backing store: ``$LYCHSIM_HOME/paths.json``. Schema is described in
``TODO_toolset.md`` section 3.9. Writes are atomic (tempfile + ``os.replace``)
to survive a crash mid-write.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

from .home import ensure_lychsim_home, get_lychsim_home


PATHS_FILE_NAME = "paths.json"
SCHEMA_VERSION = 1


def get_paths_file() -> Path:
    return get_lychsim_home() / PATHS_FILE_NAME


def load_paths() -> Dict[str, Any]:
    """Read ``paths.json``. Returns an empty registry if the file does not exist."""
    p = get_paths_file()
    if not p.exists():
        return {"version": SCHEMA_VERSION, "envs": {}}
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("version", SCHEMA_VERSION)
    data.setdefault("envs", {})
    return data


def save_paths(data: Dict[str, Any]) -> Path:
    """Write ``paths.json`` atomically. Returns the path written."""
    target = get_paths_file()
    ensure_lychsim_home()
    fd, tmp = tempfile.mkstemp(prefix=".paths.", suffix=".json.tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=False)
            f.write("\n")
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise
    return target
