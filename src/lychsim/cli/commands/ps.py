"""``lychsim ps`` -- show running LychSim instances."""

from __future__ import annotations

import argparse
import json as _json
import time

from ..runs_registry import get_runs_dir, iter_live_records, reap_stale


HELP = "List running LychSim instances."


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true",
                        help="Emit the live runs list as JSON.")


def _age(started_at: str) -> str:
    try:
        from datetime import datetime
        t = datetime.fromisoformat(started_at)
    except (ValueError, TypeError):
        return "?"
    secs = max(0, time.time() - t.timestamp())
    if secs < 60:
        return f"{secs:.0f}s"
    if secs < 3600:
        return f"{secs / 60:.0f}m"
    return f"{secs / 3600:.1f}h"


def run(args: argparse.Namespace) -> int:
    reap_stale()
    rows = []
    for handle, rec in iter_live_records():
        rows.append({
            "handle": handle,
            "env": rec.get("env_name", "?"),
            "pid": rec.get("pid"),
            "ip": rec.get("ip", "127.0.0.1"),
            "port": rec.get("port"),
            "started_at": rec.get("started_at", ""),
            "age": _age(rec.get("started_at", "")),
            "log": rec.get("log_path", ""),
        })

    if args.json:
        print(_json.dumps(rows, indent=2))
        return 0

    if not rows:
        print(f"[lychsim] no running instances (runs dir: {get_runs_dir()})")
        return 0

    handle_w = max(len("HANDLE"), *(len(r["handle"]) for r in rows))
    env_w = max(len("ENV"), *(len(r["env"]) for r in rows))
    pid_w = max(len("PID"), *(len(str(r["pid"])) for r in rows))
    addr_w = max(len("IP:PORT"), *(len(f"{r['ip']}:{r['port']}") for r in rows))
    print(f"{'HANDLE':<{handle_w}}  {'ENV':<{env_w}}  {'PID':>{pid_w}}  "
          f"{'IP:PORT':<{addr_w}}  AGE")
    for r in rows:
        addr = f"{r['ip']}:{r['port']}"
        print(f"{r['handle']:<{handle_w}}  {r['env']:<{env_w}}  "
              f"{r['pid']:>{pid_w}}  {addr:<{addr_w}}  {r['age']}")
    return 0
