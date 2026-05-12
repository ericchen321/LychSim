"""``lychsim engine`` -- manage UE engine installs (list / add / remove)."""

from __future__ import annotations

import argparse
import json as _json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from ..engine_lookup import (
    DiscoveredEngine,
    _engine_binary_in_root,
    discover_engines,
)
from ..path_registry import get_paths_file, load_paths, save_paths


HELP = "Manage UE engine installs (list, add, remove)."

LONG_DESCRIPTION = """\
Subcommands:

  lychsim engine list [--json]
      Show every engine the CLI knows about: ones registered via
      `engine add`, plus auto-discovered installs at the canonical
      install path for this platform. Sources are labelled.

  lychsim engine add <name> <path> [--force]
      Register an engine. <path> may be the engine root or the
      UnrealEditor binary; either way the binary must exist on disk.
      Registered engines take priority over auto-discovery in
      `lychsim run` resolution.

  lychsim engine remove <name> [<name>...]
      Unregister one or more engines. Touches only paths.json --
      files on disk are left alone.
"""


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.description = LONG_DESCRIPTION
    parser.formatter_class = argparse.RawDescriptionHelpFormatter

    sub = parser.add_subparsers(dest="engine_command", metavar="<subcommand>")
    parser.set_defaults(func=_no_subcommand)

    p_list = sub.add_parser("list", help="List discovered + registered engines.")
    p_list.add_argument("--json", action="store_true",
                        help="Emit the engine list as JSON.")
    p_list.set_defaults(func=run_list)

    p_add = sub.add_parser("add", help="Register an engine root.")
    p_add.add_argument("name", help="Engine identifier (e.g. 5.4, custom-build).")
    p_add.add_argument("path", type=Path,
                       help="Engine root or UnrealEditor binary path.")
    p_add.add_argument("-f", "--force", action="store_true",
                       help="Overwrite an existing entry with the same name.")
    p_add.set_defaults(func=run_add)

    p_remove = sub.add_parser("remove", help="Unregister an engine.")
    p_remove.add_argument("names", nargs="+",
                          help="Engine identifier(s) to remove.")
    p_remove.set_defaults(func=run_remove)


def _no_subcommand(args: argparse.Namespace) -> int:
    print("lychsim: missing subcommand. Try one of: list, add, remove.",
          file=sys.stderr)
    print("        See: lychsim engine --help", file=sys.stderr)
    return 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _resolve_engine_root(p: Path) -> Path:
    """Accept either an engine root or the editor binary; return the root."""
    if p.is_file():
        # <root>/Engine/Binaries/<Plat>/UnrealEditor[.exe]
        cur = p.parent
        for _ in range(5):
            if (cur / "Engine").is_dir():
                return cur
            if cur.parent == cur:
                break
            cur = cur.parent
        return p.parent
    return p


def run_list(args: argparse.Namespace) -> int:
    engines: List[DiscoveredEngine] = discover_engines()

    if args.json:
        out = [{"name": e.name, "path": str(e.path), "source": e.source}
               for e in engines]
        print(_json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    if not engines:
        print("[lychsim] no engines found.")
        print("[lychsim] add one with: lychsim engine add <name> <path>")
        return 0

    name_w = max(len("NAME"), *(len(e.name) for e in engines))
    src_w = max(len("SOURCE"), *(len(e.source) for e in engines))
    print(f"{'NAME':<{name_w}}  {'SOURCE':<{src_w}}  PATH")
    for e in engines:
        print(f"{e.name:<{name_w}}  {e.source:<{src_w}}  {e.path}")
    return 0


def run_add(args: argparse.Namespace) -> int:
    if not args.path.exists():
        print(f"lychsim: path does not exist: {args.path}", file=sys.stderr)
        return 2

    root = _resolve_engine_root(args.path.resolve())
    binary = _engine_binary_in_root(root)
    if not binary.exists():
        print(f"lychsim: no UnrealEditor binary at {binary}", file=sys.stderr)
        print("        Expected layout: <root>/Engine/Binaries/<Platform>/UnrealEditor[.exe]",
              file=sys.stderr)
        return 2

    data = load_paths()
    engines: dict = data.setdefault("engines", {})

    if args.name in engines and not args.force:
        print(f"lychsim: engine {args.name!r} already registered "
              "(use --force to overwrite).", file=sys.stderr)
        return 1

    was_present = args.name in engines
    engines[args.name] = {
        "path": str(root),
        "added_at": _now_iso(),
    }
    save_paths(data)

    verb = "overwrote" if was_present else "added"
    print(f"[lychsim] {verb}: {args.name} -> {root}")
    print(f"[lychsim] paths file: {get_paths_file()}")
    return 0


def run_remove(args: argparse.Namespace) -> int:
    data = load_paths()
    engines: dict = data.setdefault("engines", {})

    missing: List[str] = []
    removed: List[str] = []
    for name in args.names:
        if name in engines:
            del engines[name]
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
        if not removed:
            return 2
        return 1
    return 0
