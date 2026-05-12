"""``lychsim run`` -- launch a registered UE binary in the background."""

from __future__ import annotations

import argparse
import sys
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from pathlib import Path
from typing import Optional

from ..engine_lookup import engine_version_from_path, find_engine_binary
from ..interactive import pick_env
from ..launch import probe_free_port, read_default_port, spawn_detached, wait_ready
from ..path_registry import load_paths
from ..runs_registry import (
    LOG_FILE_NAME,
    allocate_handle,
    get_runs_dir,
    now_iso,
    reap_stale,
    save_record,
)


_DEFAULT_TIMEOUT_RUNTIME = 60.0
_DEFAULT_TIMEOUT_PROJECT = 300.0   # first launch shader-compiles for minutes


HELP = "Launch a registered UE binary or .uproject in the background; print ip/port when ready."

LONG_DESCRIPTION = """\
Resolves <env> to a registered entry in ~/.lychsim/paths.json, picks a free
port, and spawns UE detached. The CLI exits as soon as UE is listening; UE
keeps running until you call `lychsim stop`.

Supports both kinds:
  - kind=runtime: launches the registered .exe/.app/.sh directly.
  - kind=project: launches `UnrealEditor.exe <project>.uproject -game`,
                  using the first engine found in this order:
                    1. --engine flag (engine root or editor binary)
                    2. $UE_ENGINE_DIR
                    3. Epic Games LauncherInstalled.dat (Windows)
                    4. C:\\Program Files\\Epic Games\\UE_<ver>\\ (Windows)

If <env> is omitted (or --pick is passed), an arrow-key picker opens.
"""


def _cli_version() -> str:
    try:
        return _pkg_version("lychsim")
    except PackageNotFoundError:
        return "unknown"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.description = LONG_DESCRIPTION
    parser.formatter_class = argparse.RawDescriptionHelpFormatter
    parser.add_argument("env", nargs="?", help="Registered env name (omit to pick interactively).")
    parser.add_argument("--pick", action="store_true", help="Force the picker even with a name.")
    parser.add_argument("--no-interactive", action="store_true",
                        help="Disable the picker; require an explicit name.")
    parser.add_argument("--port", type=int, default=None,
                        help="Force a specific UnrealCV port (default: auto-pick from binary's unrealcv.ini).")
    parser.add_argument("--offscreen", action="store_true",
                        help="Pass -RenderOffScreen to UE (headless rendering).")
    parser.add_argument("--timeout", type=float, default=None,
                        help="Readiness timeout in seconds (default 60 for runtime, 300 for project).")
    parser.add_argument("--engine", type=Path, default=None,
                        help="Project mode: engine root or UnrealEditor binary path "
                             "(overrides auto-discovery).")
    parser.add_argument("--map", default=None,
                        help="Project mode: map name to load (e.g. /Game/Maps/Lobby). "
                             "Default: project's GameDefaultMap.")
    parser.add_argument("--force", action="store_true",
                        help="Project mode: launch even if the LychSim plugin is not enabled.")
    parser.add_argument("--extra-arg", action="append", default=[],
                        help="Extra UE command-line argument; repeat for several.")


def _resolve(args: argparse.Namespace) -> str | None:
    """Resolve the env name to use. Returns None on cancel."""
    data = load_paths()
    envs = data.get("envs", {}) or {}
    if not envs:
        print("lychsim: no registered envs. Use `lychsim env add <path>` first.",
              file=sys.stderr)
        return None

    if args.env and not args.pick:
        if args.env not in envs:
            print(f"lychsim: no env named {args.env!r}. Try `lychsim env list`.",
                  file=sys.stderr)
            return None
        return args.env

    if args.no_interactive:
        print("lychsim: --no-interactive requires an explicit env name.", file=sys.stderr)
        return None

    chosen = pick_env(envs)
    if chosen is None:
        print("[lychsim] cancelled.")
        return None
    return chosen


def _spawn_and_wait(
    *,
    name: str,
    rec: dict,
    binary: Path,
    cmd: list,
    timeout: float,
    uproject: Optional[Path] = None,
    map_arg: Optional[str] = None,
) -> int:
    """Shared launch flow: probe port, allocate handle, spawn, write record, wait."""
    reap_stale()

    # Caller embeds f"-UnrealCVPort={port}" in cmd; pull it back out for the record.
    port = next(
        int(a.split("=", 1)[1]) for a in cmd if a.startswith("-UnrealCVPort=")
    )

    handle, run_dir = allocate_handle(name)
    log_path = run_dir / LOG_FILE_NAME

    print(f"[lychsim] env: {name} ({rec.get('kind')}) -> {binary}")
    if uproject:
        print(f"[lychsim] uproject: {uproject}")
    if map_arg:
        print(f"[lychsim] map: {map_arg}")
    print(f"[lychsim] handle: {handle}")
    print(f"[lychsim] log: {log_path}")

    try:
        pid = spawn_detached(cmd, log_path)
    except OSError as e:
        print(f"lychsim: failed to spawn: {e}", file=sys.stderr)
        return 1

    record = {
        "handle": handle,
        "env_name": name,
        "source_kind": rec.get("kind"),
        "binary": str(binary),
        "uproject": str(uproject) if uproject else None,
        "map": map_arg,
        "pid": pid,
        "ip": "127.0.0.1",
        "port": port,
        "started_at": now_iso(),
        "log_path": str(log_path),
        "lychsim_cli_version": _cli_version(),
        "cmd": cmd,
    }
    save_record(run_dir, record)

    print(f"[lychsim] starting (pid={pid})")
    print(f"[lychsim] waiting for UnrealCV port {port}... (timeout {timeout:.0f}s)")
    elapsed = wait_ready(port, timeout=timeout)
    if elapsed is None:
        print(f"[lychsim] timed out after {timeout:.0f}s waiting for port {port}.")
        print(f"[lychsim] UE may still be loading (project mode first launch can take "
              f"several minutes for shader compilation). Inspect: {log_path}")
        print(f"[lychsim] stop with: lychsim stop {handle}")
        return 3

    print(f"[lychsim] ready in {elapsed:.1f}s")
    print(f"[lychsim] ip=127.0.0.1 port={port}")
    print(f"[lychsim] stop with: lychsim stop {handle}")
    return 0


def _run_runtime(args: argparse.Namespace, name: str, rec: dict) -> int:
    binary = Path(rec["path"])
    if not binary.exists():
        print(f"lychsim: binary missing on disk: {binary}", file=sys.stderr)
        return 2

    default_port = args.port if args.port is not None else read_default_port(binary)
    try:
        port = probe_free_port(default_port)
    except RuntimeError as e:
        print(f"lychsim: {e}", file=sys.stderr)
        return 1

    cmd = [str(binary), f"-UnrealCVPort={port}"]
    if args.offscreen:
        cmd.append("-RenderOffScreen")
    cmd.extend(args.extra_arg)

    timeout = args.timeout if args.timeout is not None else _DEFAULT_TIMEOUT_RUNTIME
    return _spawn_and_wait(name=name, rec=rec, binary=binary, cmd=cmd, timeout=timeout)


def _run_project(args: argparse.Namespace, name: str, rec: dict) -> int:
    uproject = Path(rec["path"])
    if not uproject.exists():
        print(f"lychsim: .uproject missing on disk: {uproject}", file=sys.stderr)
        return 2

    if not rec.get("has_lychsim_plugin"):
        msg = (f"lychsim: env {name!r} does not have the LychSim plugin enabled in its "
               f".uproject (Plugins[]). UnrealCV calls will fail.")
        if args.force:
            print(f"[lychsim] WARNING: {msg} (proceeding because --force)")
        else:
            print(msg, file=sys.stderr)
            print("        Pass --force to launch anyway, or enable the plugin in "
                  f"{uproject}.", file=sys.stderr)
            return 1

    engine_version = rec.get("engine_version")
    engine_bin = find_engine_binary(engine_version=engine_version, override=args.engine)
    if engine_bin is None:
        print("lychsim: could not locate UnrealEditor for this project.", file=sys.stderr)
        if engine_version:
            print(f"        Looking for engine version: {engine_version}", file=sys.stderr)
        print("        Try one of:", file=sys.stderr)
        print("          --engine \"C:\\Program Files\\Epic Games\\UE_5.4\"", file=sys.stderr)
        print("          --engine \"...\\UnrealEditor.exe\"", file=sys.stderr)
        print("          set UE_ENGINE_DIR=<engine root> in the environment", file=sys.stderr)
        return 2
    detected_ver = engine_version_from_path(engine_bin)
    if engine_version and detected_ver and detected_ver != engine_version:
        print(
            f"[lychsim] WARNING: project requires engine {engine_version}, "
            f"but using {detected_ver}. UE may prompt to upgrade the project, "
            "or fail to load. Pass --engine to pin a different install."
        )
    print(f"[lychsim] engine: {engine_bin}" + (f" (v{detected_ver})" if detected_ver else ""))

    default_port = args.port if args.port is not None else read_default_port(engine_bin)
    try:
        port = probe_free_port(default_port)
    except RuntimeError as e:
        print(f"lychsim: {e}", file=sys.stderr)
        return 1

    map_arg = args.map or rec.get("default_map")

    # UE project-mode launch: <editor> <project.uproject> [Map] -game -UnrealCVPort=N ...
    cmd = [str(engine_bin), str(uproject)]
    if map_arg:
        cmd.append(map_arg)
    cmd.append("-game")
    cmd.append(f"-UnrealCVPort={port}")
    if args.offscreen:
        cmd.append("-RenderOffScreen")
    cmd.extend(args.extra_arg)

    timeout = args.timeout if args.timeout is not None else _DEFAULT_TIMEOUT_PROJECT
    return _spawn_and_wait(
        name=name, rec=rec, binary=engine_bin, cmd=cmd,
        timeout=timeout, uproject=uproject, map_arg=map_arg,
    )


def run(args: argparse.Namespace) -> int:
    name = _resolve(args)
    if name is None:
        return 1
    rec = load_paths()["envs"][name]
    kind = rec.get("kind")
    if kind == "runtime":
        return _run_runtime(args, name, rec)
    if kind == "project":
        return _run_project(args, name, rec)
    print(f"lychsim: env {name!r} has unknown kind {kind!r}", file=sys.stderr)
    return 1
