"""Arrow-key env picker for ``lychsim run``.

Uses ``questionary`` when installed and stdout is a tty; otherwise falls
back to a numbered prompt. Returns the selected env name (a key in
``paths.json``'s ``envs`` map), or ``None`` if the user cancelled.
"""

from __future__ import annotations

import sys
from typing import Optional


def _can_use_questionary() -> bool:
    if not sys.stdout.isatty():
        return False
    try:
        import questionary  # noqa: F401
        return True
    except ImportError:
        return False


def _label(name: str, rec: dict) -> str:
    kind = rec.get("kind", "?")
    path = rec.get("path", "")
    extras = []
    if kind == "project":
        eng = rec.get("engine_version") or "?"
        plugin = "ok" if rec.get("has_lychsim_plugin") else "missing"
        extras.append(f"engine={eng}")
        extras.append(f"plugin={plugin}")
    extra_str = ("  " + " ".join(extras)) if extras else ""
    return f"{name}  ({kind}){extra_str}  {path}"


def _numbered(envs: dict) -> Optional[str]:
    names = sorted(envs.keys())
    print("[lychsim] choose an env to launch:")
    for i, name in enumerate(names, 1):
        print(f"  {i}) {_label(name, envs[name])}")
    while True:
        try:
            ans = input("number (or empty to cancel) > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if not ans:
            return None
        try:
            idx = int(ans) - 1
        except ValueError:
            print(f"  not a number: {ans!r}")
            continue
        if 0 <= idx < len(names):
            return names[idx]
        print(f"  out of range: {ans}")


def pick_env(envs: dict) -> Optional[str]:
    if not envs:
        return None
    if not _can_use_questionary():
        return _numbered(envs)
    import questionary
    names = sorted(envs.keys())
    choices = [questionary.Choice(_label(n, envs[n]), value=n) for n in names]
    return questionary.select("Choose an env to launch:", choices=choices).ask()
