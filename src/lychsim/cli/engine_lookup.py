"""Locate UnrealEditor binaries for project-mode launches.

Resolution order in :func:`find_engine_binary`:

  1. ``--engine`` CLI override (a root dir or the editor binary)
  2. ``$UE_ENGINE_DIR`` env var
  3. Engines registered via ``lychsim engine add`` (paths.json -> engines)
  4. Canonical install-path scan (one location per platform, see below)

Only one path is scanned per platform on purpose -- this keeps the v1
discovery simple and predictable. Users with non-default installs (custom
drives, source builds, multi-version setups) can pin via ``--engine``,
``$UE_ENGINE_DIR``, or ``lychsim engine add``.

Future improvement: more sophisticated discovery -- Windows registry under
``HKLM/HKCU\\SOFTWARE\\Epic Games\\Unreal Engine\\Builds`` (catches source
builds + Launcher installs to non-default drives), ``LauncherInstalled.dat``,
``~/.config/Epic`` files on Linux, ``/Applications/Epic Games`` on macOS.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class DiscoveredEngine:
    name: str           # version like "5.5", or whatever name engine add used
    path: Path          # full path to the editor binary
    source: str         # "registered" | "discovered"


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def engine_version_from_path(path: Path) -> Optional[str]:
    """Extract ``5.4`` from a path containing ``UE_5.4``. Returns None on no match."""
    for part in path.parts:
        if part.startswith("UE_") and len(part) > 3:
            return part[len("UE_"):]
    return None


def _engine_binary_in_root(root: Path) -> Path:
    """Return the platform-specific editor binary inside an engine root."""
    if sys.platform.startswith("win"):
        return root / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe"
    if sys.platform.startswith("darwin"):
        return root / "Engine" / "Binaries" / "Mac" / "UnrealEditor.app" / "Contents" / "MacOS" / "UnrealEditor"
    return root / "Engine" / "Binaries" / "Linux" / "UnrealEditor"


def _version_tuple(s: str) -> tuple:
    parts = s.split(".")
    out: list = []
    for p in parts:
        if not p.isdigit():
            return (0,)
        out.append(int(p))
    return tuple(out)


def _norm(p: Path) -> str:
    return os.path.normcase(os.path.normpath(str(p)))


# ---------------------------------------------------------------------------
# Discovery sources
# ---------------------------------------------------------------------------

def _canonical_discovery() -> List[DiscoveredEngine]:
    """Single canonical scan per platform.

    - Windows: ``C:\\Program Files\\Epic Games\\UE_*`` (Epic Launcher default).
    - macOS:   ``/Users/Shared/Epic Games/UE_*``       (Epic Launcher default).
    - Linux:   ``~/UnrealEngine``                       (source-build default).
    """
    out: List[DiscoveredEngine] = []
    if sys.platform.startswith("win"):
        base = Path(r"C:\Program Files\Epic Games")
        if base.exists():
            for d in sorted(base.glob("UE_*")):
                if not d.is_dir():
                    continue
                bin_path = _engine_binary_in_root(d)
                if bin_path.exists():
                    out.append(DiscoveredEngine(
                        name=d.name[len("UE_"):], path=bin_path, source="discovered",
                    ))
    elif sys.platform.startswith("darwin"):
        base = Path("/Users/Shared/Epic Games")
        if base.exists():
            for d in sorted(base.glob("UE_*")):
                if not d.is_dir():
                    continue
                bin_path = _engine_binary_in_root(d)
                if bin_path.exists():
                    out.append(DiscoveredEngine(
                        name=d.name[len("UE_"):], path=bin_path, source="discovered",
                    ))
    elif sys.platform.startswith("linux"):
        d = Path.home() / "UnrealEngine"
        if d.exists():
            bin_path = _engine_binary_in_root(d)
            if bin_path.exists():
                out.append(DiscoveredEngine(
                    name="UnrealEngine", path=bin_path, source="discovered",
                ))
    return out


def _registered_engines() -> List[DiscoveredEngine]:
    """Engines persisted under ``paths.json`` -> ``engines`` (via ``engine add``)."""
    # Local import to avoid an import cycle: path_registry -> home, no engine_lookup.
    from .path_registry import load_paths
    data = load_paths()
    engines = data.get("engines") or {}
    out: List[DiscoveredEngine] = []
    for name, rec in engines.items():
        if not isinstance(rec, dict):
            continue
        raw = rec.get("path")
        if not raw:
            continue
        p = Path(raw)
        bin_path = p if p.is_file() else _engine_binary_in_root(p)
        if bin_path.exists():
            out.append(DiscoveredEngine(name=name, path=bin_path, source="registered"))
    return out


def discover_engines() -> List[DiscoveredEngine]:
    """All known engines: registered first, then canonical scan, deduped by path."""
    seen = set()
    out: List[DiscoveredEngine] = []
    for e in _registered_engines() + _canonical_discovery():
        key = _norm(e.path)
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


# ---------------------------------------------------------------------------
# Resolution for `lychsim run`
# ---------------------------------------------------------------------------

def _resolve_override(override: Path) -> Optional[Path]:
    """``--engine`` accepts either an engine root or the editor binary directly."""
    if override.is_file():
        return override if override.exists() else None
    if override.is_dir():
        cand = _engine_binary_in_root(override)
        return cand if cand.exists() else None
    return None


def find_engine_binary(
    engine_version: Optional[str] = None,
    override: Optional[Path] = None,
) -> Optional[Path]:
    """Locate ``UnrealEditor`` for project mode. Returns ``None`` if no match."""
    if override is not None:
        return _resolve_override(override)

    env_dir = os.environ.get("UE_ENGINE_DIR")
    if env_dir:
        p = _engine_binary_in_root(Path(env_dir))
        if p.exists():
            return p

    candidates = discover_engines()
    if not candidates:
        return None

    if engine_version:
        for e in candidates:
            if e.name == engine_version:
                return e.path

    # Fall back to highest version-like name (or first if none parse as versions).
    sortable = [(e, _version_tuple(e.name)) for e in candidates]
    sortable.sort(key=lambda x: x[1])
    return sortable[-1][0].path
