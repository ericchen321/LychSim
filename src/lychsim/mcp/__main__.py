"""Entry point for ``python -m lychsim.mcp`` and the ``lychsim-mcp`` script.

Runs the FastMCP server over stdio. Stdio is the transport used by
Claude Desktop and Claude Code; other transports are not supported yet.
"""

from __future__ import annotations

import logging

from .server import close_sim, mcp


def main() -> None:
    # Log to stderr. stdout is reserved for the MCP stdio protocol —
    # writing to it would corrupt the JSON-RPC stream.
    logging.basicConfig(level=logging.INFO)
    try:
        mcp.run(transport="stdio")
    finally:
        close_sim()


if __name__ == "__main__":
    main()
