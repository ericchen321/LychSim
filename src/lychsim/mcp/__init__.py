"""MCP server for LychSim.

Exposes the LychSim Python API as Model Context Protocol tools so that
LLM clients (e.g., Claude Desktop, Claude Code) can query a running
Unreal Engine instance that has the LychSim plugin loaded.
"""

from .server import mcp

__all__ = ["mcp"]
