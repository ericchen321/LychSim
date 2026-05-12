"""``lychsim env`` -- manage the registered envs (list / add / remove)."""

from __future__ import annotations

import argparse
import json as _json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

from ..path_detect import DetectedEntry, detect
from ..path_registry import get_paths_file, load_paths, save_paths


HELP = "Manage registered UE projects and binaries (list, add, remove)."

LONG_DESCRIPTION = """\
Subcommands:

  lychsim env list [--json]
      Show every registered env (name, kind, path, project metadata).
      Path-missing-on-disk entries are flagged. --json dumps the raw
      envs object.

  lychsim env add <path> [--name N] [-f|--force]
      Detect what lives at <path> and register it. Accepts a .uproject,
      an executable (.exe/.sh/.app), or a directory containing one or
      more projects directly (*.uproject), direct executables, or
      *.uproject in immediate subdirs (parent-of-projects layout).

  lychsim env remove <name> [<name>...]
      Remove one or more entries. Touches only paths.json -- files on
      disk are left alone.
"""


# ---------------------------------------------------------------------------
# env list
# ---------------------------------------------------------------------------

def _project_notes(rec: dict) -> list:
    notes = [
        f"engine={rec.get('engine_version') or '?'}",
        f"plugin={'ok' if rec.get('has_lychsim_plugin') else 'missing'}",
    ]
    if rec.get("default_map"):
        notes.append(f"map={rec['default_map']}")
    return notes


def run_list(args: argparse.Namespace) -> int:
    data = load_paths()
    envs = data.get("envs", {}) or {}
    paths_file = get_paths_file()

    if args.json:
        print(_json.dumps(envs, indent=2, ensure_ascii=False))
        return 0

    if not envs:
        print(f"[lychsim] no registered envs in {paths_file}")
        print("[lychsim] add one with: lychsim env add <path>")
        return 0

    rows = []
    for name in sorted(envs.keys()):
        rec = envs[name]
        kind = rec.get("kind", "?")
        path_str = rec.get("path", "")
        notes: list = []
        if path_str and not Path(path_str).exists():
            notes.append("MISSING")
        if kind == "project":
            notes.extend(_project_notes(rec))
        rows.append((name, kind, path_str, " ".join(notes)))

    name_w = max(len("NAME"), *(len(r[0]) for r in rows))
    kind_w = max(len("KIND"), *(len(r[1]) for r in rows))
    print(f"{'NAME':<{name_w}}  {'KIND':<{kind_w}}  PATH")
    for name, kind, path_str, notes in rows:
        line = f"{name:<{name_w}}  {kind:<{kind_w}}  {path_str}"
        if notes:
            line += "  " + notes
        print(line)
    print()
    plural = "" if len(envs) == 1 else "s"
    print(f"[lychsim] paths file: {paths_file} ({len(envs)} env{plural})")
    return 0


# ---------------------------------------------------------------------------
# env add
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _format_row(e: DetectedEntry) -> str:
    parts = [f"  {e.name:<24}", f"{e.kind:<8}", str(e.path)]
    if e.kind == "project":
        eng = e.engine_version or "?"
        plugin = "ok" if e.has_lychsim_plugin else "missing"
        parts.append(f"engine={eng}")
        parts.append(f"plugin={plugin}")
    return "  ".join(parts)


def _to_record(e: DetectedEntry, when: str) -> dict:
    rec = {
        "kind": e.kind,
        "path": str(e.path),
        "added_at": when,
    }
    if e.kind == "project":
        rec["engine_version"] = e.engine_version
        rec["has_lychsim_plugin"] = bool(e.has_lychsim_plugin)
        if e.default_map:
            rec["default_map"] = e.default_map
    return rec


def run_add(args: argparse.Namespace) -> int:
    try:
        entries = detect(args.path)
    except (FileNotFoundError, ValueError) as e:
        print(f"lychsim: {e}", file=sys.stderr)
        return 2

    if args.name and len(entries) != 1:
        print(
            f"lychsim: --name can only be used when the path resolves to a single entry "
            f"(got {len(entries)})",
            file=sys.stderr,
        )
        return 1
    if args.name:
        entries[0].name = args.name

    print(f"[lychsim] detected {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}:")
    for e in entries:
        print(_format_row(e))
        for w in e.warnings:
            print(f"    note: {w}")

    data = load_paths()
    envs: dict = data.setdefault("envs", {})
    when = _now_iso()

    added: List[str] = []
    overwritten: List[str] = []
    skipped: List[Tuple[str, str]] = []

    for e in entries:
        if e.name in envs and not args.force:
            skipped.append((e.name, "already registered (use --force to overwrite)"))
            continue
        was_present = e.name in envs
        envs[e.name] = _to_record(e, when)
        (overwritten if was_present else added).append(e.name)

    if added or overwritten:
        save_paths(data)
        print(f"[lychsim] paths file: {get_paths_file()}")
    else:
        print(f"[lychsim] paths file: {get_paths_file()} (unchanged)")

    if added:
        print(f"[lychsim] added: {', '.join(added)}")
    if overwritten:
        print(f"[lychsim] overwritten: {', '.join(overwritten)}")
    for name, reason in skipped:
        print(f"[lychsim] skipped {name}: {reason}", file=sys.stderr)

    if skipped and not (added or overwritten):
        return 1
    return 0


# ---------------------------------------------------------------------------
# env remove
# ---------------------------------------------------------------------------

def run_remove(args: argparse.Namespace) -> int:
    data = load_paths()
    envs: dict = data.setdefault("envs", {})

    missing: List[str] = []
    removed: List[str] = []
    for name in args.names:
        if name in envs:
            del envs[name]
            removed.append(name)
        else:
            missing.append(name)

    if removed:
        save_paths(data)
        print(f"[lychsim] removed: {', '.join(removed)}")
        print(f"[lychsim] paths file: {get_paths_file()}")
    else:
        print(f"[lychsim] paths file: {get_paths_file()} (unchanged)")

    if missing:
        print(f"lychsim: not registered: {', '.join(missing)}", file=sys.stderr)

    if missing and not removed:
        return 2
    if missing:
        return 1
    return 0


# ---------------------------------------------------------------------------
# argparse glue
# ---------------------------------------------------------------------------

_ADD_LONG_DESCRIPTION = """\
Detects what lives at <path> and registers it. Accepts:

  Single asset:
    - a .uproject file                                -> one project
    - an executable: .exe (Windows), .sh (Linux),
      .app bundle (macOS)                             -> one runtime

  Directory of UE projects or binaries:
    - directory with *.uproject directly inside       -> one project per match
    - directory with platform-native executables
      directly inside (.exe / .sh / .app)             -> one runtime per match
    - directory with */*.uproject in immediate
      subdirs (parent-of-projects layout)             -> one project per match

If both .uproject and executable files are present at the same level,
projects take precedence. Use --name to override only when the input
resolves to exactly one entry.
"""


def _no_subcommand(args: argparse.Namespace) -> int:
    print("lychsim: missing subcommand. Try one of: list, add, remove.",
          file=sys.stderr)
    print("        See: lychsim env --help", file=sys.stderr)
    return 1


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.description = LONG_DESCRIPTION
    parser.formatter_class = argparse.RawDescriptionHelpFormatter

    sub = parser.add_subparsers(dest="env_command", metavar="<subcommand>")
    parser.set_defaults(func=_no_subcommand)

    p_list = sub.add_parser("list", help="List registered envs.")
    p_list.add_argument("--json", action="store_true",
                        help="Emit the registry as JSON.")
    p_list.set_defaults(func=run_list)

    p_add = sub.add_parser("add", help="Register a UE project, binary, or directory.")
    p_add.description = _ADD_LONG_DESCRIPTION
    p_add.formatter_class = argparse.RawDescriptionHelpFormatter
    p_add.add_argument("path", type=Path, help="Filesystem path to register.")
    p_add.add_argument("--name", default=None,
                       help="Override the registered name (only when input resolves to one entry).")
    p_add.add_argument("-f", "--force", action="store_true",
                       help="Overwrite existing entries with the same name.")
    p_add.set_defaults(func=run_add)

    p_remove = sub.add_parser("remove", help="Remove one or more registered envs.")
    p_remove.add_argument("names", nargs="+",
                          help="Registered env name(s) to remove.")
    p_remove.set_defaults(func=run_remove)
