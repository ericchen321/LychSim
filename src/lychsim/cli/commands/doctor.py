"""``lychsim doctor`` -- run sanity checks and surface configuration issues."""

from __future__ import annotations

import argparse
import importlib
import json as _json
import socket
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

from ..engine_lookup import discover_engines, find_engine_binary
from ..home import get_lychsim_home
from ..path_registry import get_paths_file, load_paths
from ..runs_registry import iter_live_records, reap_stale


HELP = "Run sanity checks: registered envs, engine discovery, GPU, port, etc."

LONG_DESCRIPTION = """\
Walks through environment, registry, and system checks and prints a status
line for each. Exit 0 if no failures, exit 1 if any FAIL. Warnings and INFO
lines do not affect exit code.

Per-env entries that pass are hidden by default to keep the output scannable;
pass --verbose to see them. --json emits machine-readable output (always full).
"""


@dataclass
class CheckResult:
    name: str
    status: str  # "ok" | "warn" | "fail" | "info"
    message: str
    hint: Optional[str] = None


_LABEL = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL", "info": "INFO"}


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.description = LONG_DESCRIPTION
    parser.formatter_class = argparse.RawDescriptionHelpFormatter
    parser.add_argument("--json", action="store_true",
                        help="Emit results as JSON instead of the table.")
    parser.add_argument("--verbose", action="store_true",
                        help="Show passing per-env checks too (default hides them).")


# ---------------------------------------------------------------------------
# Setup checks
# ---------------------------------------------------------------------------

def _check_lychsim_home() -> CheckResult:
    home = get_lychsim_home()
    msg = str(home)
    if not home.exists():
        msg += " (does not exist yet)"
    return CheckResult(name="$LYCHSIM_HOME", status="info", message=msg)


def _check_paths_file() -> CheckResult:
    p = get_paths_file()
    if not p.exists():
        return CheckResult(
            name="paths.json", status="info",
            message=f"not yet created ({p})",
        )
    try:
        data = load_paths()
    except (OSError, ValueError) as e:
        return CheckResult(
            name="paths.json", status="fail",
            message=f"could not parse: {e}",
            hint=f"inspect {p} or delete it to start fresh",
        )
    n_envs = len(data.get("envs", {}) or {})
    n_engines = len(data.get("engines", {}) or {})
    return CheckResult(
        name="paths.json", status="ok",
        message=f"present, {n_envs} envs / {n_engines} engines registered",
    )


def _check_module(name: str, *, optional: bool = False, hint: Optional[str] = None) -> CheckResult:
    try:
        m = importlib.import_module(name)
        ver = getattr(m, "__version__", "unknown")
        return CheckResult(name=name, status="ok", message=str(ver))
    except ImportError:
        if optional:
            return CheckResult(name=name, status="warn",
                               message="not installed (optional)", hint=hint)
        return CheckResult(name=name, status="fail",
                           message="not installed", hint=hint)


# ---------------------------------------------------------------------------
# Registry-content checks
# ---------------------------------------------------------------------------

def _check_envs_count(data: dict) -> CheckResult:
    envs = data.get("envs", {}) or {}
    if not envs:
        return CheckResult(
            name="envs", status="warn",
            message="no envs registered",
            hint="lychsim env add <path>",
        )
    return CheckResult(name="envs", status="ok", message=f"{len(envs)} registered")


def _check_engines() -> CheckResult:
    engines = discover_engines()
    if not engines:
        return CheckResult(
            name="engines", status="warn",
            message="no engine found via canonical scan or registration",
            hint="install UE via Epic Launcher, or `lychsim engine add <name> <path>`",
        )
    by_source: dict = {}
    for e in engines:
        by_source[e.source] = by_source.get(e.source, 0) + 1
    parts = ", ".join(f"{c} {s}" for s, c in by_source.items())
    return CheckResult(name="engines", status="ok", message=parts)


def _check_each_env(data: dict) -> List[CheckResult]:
    out: List[CheckResult] = []
    envs = data.get("envs", {}) or {}
    for name in sorted(envs.keys()):
        rec = envs[name]
        kind = rec.get("kind", "?")
        path_str = rec.get("path", "")
        path = Path(path_str)

        if not path.exists():
            out.append(CheckResult(
                name=f"env: {name}", status="fail",
                message=f"path missing on disk: {path}",
                hint=f"`lychsim env remove {name}`, or restore the file",
            ))
            continue

        if kind == "project":
            if not rec.get("has_lychsim_plugin"):
                out.append(CheckResult(
                    name=f"env: {name}", status="warn",
                    message="LychSim plugin not enabled in .uproject (UnrealCV calls will fail)",
                    hint=f"enable LychSim in {path}",
                ))
                continue
            engine_ver = rec.get("engine_version")
            engine_bin = find_engine_binary(engine_version=engine_ver)
            if engine_bin is None:
                out.append(CheckResult(
                    name=f"env: {name}", status="fail",
                    message=f"no engine resolvable for version {engine_ver!r}",
                    hint="`lychsim engine add <name> <path>`, or pass --engine to `lychsim run`",
                ))
                continue
            out.append(CheckResult(
                name=f"env: {name}", status="ok",
                message=f"project, plugin ok, engine {engine_ver or '?'} resolved",
            ))
        else:
            out.append(CheckResult(
                name=f"env: {name}", status="ok",
                message="runtime, binary present",
            ))
    return out


# ---------------------------------------------------------------------------
# System checks
# ---------------------------------------------------------------------------

def _check_gpu() -> CheckResult:
    """Best-effort GPU detection via nvidia-smi. Falls back to INFO."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return CheckResult(
            name="GPU", status="info",
            message="nvidia-smi not available; LychSim should work with any UE-supported GPU",
        )
    if result.returncode != 0 or not result.stdout.strip():
        return CheckResult(
            name="GPU", status="info",
            message="nvidia-smi present but reported no GPUs",
        )
    lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
    if len(lines) == 1:
        return CheckResult(name="GPU", status="ok", message=lines[0])
    return CheckResult(
        name="GPU", status="ok",
        message=f"{len(lines)} GPUs: " + "; ".join(lines),
    )


def _check_port_9000() -> CheckResult:
    """Probe whether 127.0.0.1:9000 (LychSim's default) is bindable now."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 9000))
        return CheckResult(name="port 9000", status="ok", message="free")
    except OSError:
        return CheckResult(
            name="port 9000", status="info",
            message="in use (will auto-bump on `lychsim run`)",
        )


def _check_live_runs() -> CheckResult:
    reap_stale()
    rows = list(iter_live_records())
    if not rows:
        return CheckResult(name="live runs", status="info", message="none")
    handles = ", ".join(h for h, _ in rows)
    return CheckResult(
        name="live runs", status="info",
        message=f"{len(rows)} ({handles})",
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _collect() -> List[CheckResult]:
    results: List[CheckResult] = []
    results.append(_check_lychsim_home())
    results.append(_check_paths_file())
    results.append(_check_module("psutil"))
    results.append(_check_module(
        "questionary", optional=True,
        hint="pip install -e .[interactive] for arrow-key picker",
    ))

    try:
        data = load_paths()
    except (OSError, ValueError):
        data = {"envs": {}, "engines": {}}

    results.append(_check_envs_count(data))
    results.append(_check_engines())
    results.extend(_check_each_env(data))

    results.append(_check_gpu())
    results.append(_check_port_9000())
    results.append(_check_live_runs())
    return results


def _should_show(r: CheckResult, verbose: bool) -> bool:
    if verbose:
        return True
    if r.status != "ok":
        return True
    # Hide passing per-env entries to keep the table compact.
    return not r.name.startswith("env: ")


def _render_table(results: List[CheckResult], verbose: bool) -> None:
    visible = [r for r in results if _should_show(r, verbose)]
    if not visible:
        print("[lychsim] no issues found.")
        return
    name_w = max(len("CHECK"), *(len(r.name) for r in visible))
    for r in visible:
        label = _LABEL.get(r.status, "?   ")
        print(f"  {label}  {r.name:<{name_w}}  {r.message}")
        if r.hint:
            print(f"        {' ' * name_w}  hint: {r.hint}")


def run(args: argparse.Namespace) -> int:
    results = _collect()

    if args.json:
        print(_json.dumps([asdict(r) for r in results], indent=2, ensure_ascii=False))
    else:
        _render_table(results, args.verbose)
        n_fail = sum(1 for r in results if r.status == "fail")
        n_warn = sum(1 for r in results if r.status == "warn")
        n_ok = sum(1 for r in results if r.status == "ok")
        n_hidden = sum(1 for r in results
                       if r.status == "ok"
                       and r.name.startswith("env: ")
                       and not args.verbose)
        print()
        if n_fail:
            print(f"[lychsim] {n_fail} fail, {n_warn} warn, {n_ok} ok"
                  + (f" ({n_hidden} env(s) hidden, --verbose to show)" if n_hidden else ""))
        elif n_warn:
            print(f"[lychsim] {n_warn} warn (non-blocking), {n_ok} ok"
                  + (f" ({n_hidden} env(s) hidden, --verbose to show)" if n_hidden else ""))
        else:
            print(f"[lychsim] all checks passed."
                  + (f" ({n_hidden} env(s) hidden, --verbose to show)" if n_hidden else ""))

    return 1 if any(r.status == "fail" for r in results) else 0
