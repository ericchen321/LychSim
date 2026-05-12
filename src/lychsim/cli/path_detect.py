"""Detect what kind of UE asset lives at a filesystem path.

Used by ``lychsim env add`` to turn a user-supplied path into one or
more :class:`DetectedEntry` records. Accepted shapes:

- ``Foo.uproject`` file -> one project
- Executable file (``.exe`` / ``.sh`` / ``.app``) -> one runtime
- Directory containing ``*.uproject`` directly -> one project per match
- Directory containing direct executables -> one runtime per match
- Directory containing ``*/*.uproject`` -> N projects (parent layout)

If both ``.uproject`` and executables are present at the same level,
projects win (the more authoritative source).
"""

from __future__ import annotations

import configparser
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class DetectedEntry:
    name: str
    kind: str  # "project" | "runtime"
    path: Path
    engine_version: Optional[str] = None
    has_lychsim_plugin: Optional[bool] = None
    default_map: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


def _executable_file_suffixes() -> tuple:
    if sys.platform.startswith("win"):
        return (".exe",)
    if sys.platform.startswith("darwin"):
        return ()
    return (".sh",)


def _runtime_glob_patterns() -> List[str]:
    """Glob patterns for direct-executable detection inside a directory."""
    if sys.platform.startswith("win"):
        return ["*.exe"]
    if sys.platform.startswith("darwin"):
        return ["*.app"]
    return ["*.sh"]


def _glob_runtimes(d: Path) -> List[Path]:
    matches: List[Path] = []
    for pat in _runtime_glob_patterns():
        matches.extend(d.glob(pat))
    return sorted(matches)


def _is_runtime_file(path: Path) -> bool:
    if not path.is_file():
        return False
    suffix = path.suffix.lower()
    if suffix in _executable_file_suffixes():
        return True
    if sys.platform.startswith("linux") and os.access(path, os.X_OK) and suffix in ("", ".sh"):
        return True
    return False


def _is_runtime_dir(path: Path) -> bool:
    if sys.platform.startswith("darwin") and path.is_dir() and path.suffix.lower() == ".app":
        return True
    return False


def _parse_uproject(path: Path) -> tuple:
    """Return ``(engine_version, has_lychsim_plugin, warnings)``."""
    warnings: List[str] = []
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except OSError as e:
        warnings.append(f"could not read .uproject: {e}")
        return None, False, warnings
    except ValueError as e:
        warnings.append(f"could not parse .uproject JSON: {e}")
        return None, False, warnings

    engine_version = data.get("EngineAssociation") or None
    has_plugin = False
    for plugin in data.get("Plugins") or []:
        if not isinstance(plugin, dict):
            continue
        if plugin.get("Name") == "LychSim" and plugin.get("Enabled", False):
            has_plugin = True
            break
    if not has_plugin:
        warnings.append("LychSim plugin not enabled in this .uproject")
    return engine_version, has_plugin, warnings


def _parse_default_map(uproject: Path) -> Optional[str]:
    ini = uproject.parent / "Config" / "DefaultEngine.ini"
    if not ini.exists():
        return None
    cp = configparser.ConfigParser(strict=False, interpolation=None)
    try:
        cp.read(ini, encoding="utf-8-sig")
    except (configparser.Error, OSError):
        return None
    section = "/Script/EngineSettings.GameMapsSettings"
    if cp.has_section(section) and cp.has_option(section, "GameDefaultMap"):
        return cp.get(section, "GameDefaultMap").strip() or None
    return None


def _project_entry(uproject: Path) -> DetectedEntry:
    engine_version, has_plugin, warnings = _parse_uproject(uproject)
    default_map = _parse_default_map(uproject)
    return DetectedEntry(
        name=uproject.stem,
        kind="project",
        path=uproject.resolve(),
        engine_version=engine_version,
        has_lychsim_plugin=has_plugin,
        default_map=default_map,
        warnings=warnings,
    )


def _runtime_entry(executable: Path) -> DetectedEntry:
    return DetectedEntry(
        name=executable.stem,
        kind="runtime",
        path=executable.resolve(),
    )


def detect(path: Path) -> List[DetectedEntry]:
    """Inspect ``path`` and return one or more :class:`DetectedEntry`."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"path does not exist: {path}")

    if path.is_file():
        if path.suffix.lower() == ".uproject":
            return [_project_entry(path)]
        if _is_runtime_file(path):
            return [_runtime_entry(path)]
        raise ValueError(
            f"unrecognized file type: {path} "
            "(expected .uproject or an executable like .exe / .sh / .app)"
        )

    if _is_runtime_dir(path):
        return [_runtime_entry(path)]

    if path.is_dir():
        direct_proj = sorted(path.glob("*.uproject"))
        if direct_proj:
            return [_project_entry(p) for p in direct_proj]
        direct_run = _glob_runtimes(path)
        if direct_run:
            return [_runtime_entry(p) for p in direct_run]
        child_proj = sorted(path.glob("*/*.uproject"))
        if child_proj:
            return [_project_entry(p) for p in child_proj]
        raise ValueError(
            f"no .uproject or executable found under {path} "
            "(checked '*.uproject', direct executables, and '*/*.uproject')"
        )

    raise ValueError(f"path is neither file nor directory: {path}")
