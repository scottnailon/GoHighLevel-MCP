"""FastMCP server for GoHighLevel.

Tools live in :mod:`ghl_mcp.tools`. Each tool module defines a ``register(mcp)``
function that hooks its tools into the server. This file orchestrates that
registration and exposes the singleton ``mcp`` for the entrypoint to run.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ghl_mcp.tools import register_all

# The MCP server. Name follows the skill convention: ``{service}_mcp``.
mcp = FastMCP("gohighlevel_mcp")

# Wire up every tool.
register_all(mcp)


__all__ = ["mcp"]
