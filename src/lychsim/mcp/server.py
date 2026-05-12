"""FastMCP server instance and lazy LychSim connection.

Configuration is read from environment variables at process start:

    LYCHSIM_HOST   (default: "localhost")
    LYCHSIM_PORT   (default: 9000)
    LYCHSIM_WIDTH  (default: 640)
    LYCHSIM_HEIGHT (default: 480)

The LychSim client is created lazily on the first tool call via
``get_sim()``. This lets the MCP server start cleanly even when Unreal
Engine is not yet running, which matters because Claude Desktop spawns
MCP servers at app launch — an eager connect would crash the process and
the MCP integration would be marked as failed until the app is
restarted.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from mcp.server.fastmcp import FastMCP

from ..api import LychSim

logger = logging.getLogger(__name__)

mcp = FastMCP("lychsim")

_sim: Optional[LychSim] = None


def _config() -> dict:
    return {
        "server_name": os.environ.get("LYCHSIM_HOST", "localhost"),
        "port": int(os.environ.get("LYCHSIM_PORT", "9000")),
        "width": int(os.environ.get("LYCHSIM_WIDTH", "640")),
        "height": int(os.environ.get("LYCHSIM_HEIGHT", "480")),
    }


def get_sim() -> LychSim:
    """Return the shared LychSim client, connecting on first use."""
    global _sim
    if _sim is None:
        cfg = _config()
        logger.info(
            "Connecting to LychSim at %s:%d (%dx%d)",
            cfg["server_name"],
            cfg["port"],
            cfg["width"],
            cfg["height"],
        )
        _sim = LychSim(**cfg)
    return _sim


def close_sim() -> None:
    """Disconnect the shared LychSim client if one exists."""
    global _sim
    if _sim is not None:
        try:
            _sim.close()
        finally:
            _sim = None


# Tool modules register @mcp.tool() decorated functions by importing
# `mcp` and `get_sim` from this module. They are imported at the bottom
# of this file (after `mcp` / `get_sim` are defined) to avoid circular
# imports.
from .tools import camera, objects  # noqa: E402, F401
