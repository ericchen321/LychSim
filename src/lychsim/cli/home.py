"""``$LYCHSIM_HOME`` location and creation helpers."""

from __future__ import annotations

import os
from pathlib import Path


def get_lychsim_home() -> Path:
    """Resolve ``$LYCHSIM_HOME``.

    Honors the ``LYCHSIM_HOME`` env var if set; otherwise defaults to
    ``~/.lychsim``. Does not create the directory -- callers that need
    the dir to exist should use :func:`ensure_lychsim_home`.
    """
    override = os.environ.get("LYCHSIM_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".lychsim"


def ensure_lychsim_home() -> Path:
    home = get_lychsim_home()
    home.mkdir(parents=True, exist_ok=True)
    return home
