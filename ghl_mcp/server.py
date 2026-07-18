"""FastMCP server for GoHighLevel.

Tools live in :mod:`ghl_mcp.tools`. Each tool module defines a ``register(mcp)``
function that hooks its tools into the server. This file orchestrates that
registration and exposes the singleton ``mcp`` for the entrypoint to run.

Two transports share this one instance:

* stdio (default) — used by Claude Code / Claude Desktop running the server
  as a local subprocess. No auth needed; the OS process boundary is the
  security boundary. Unaffected by anything below.
* streamable-http (``GHL_MCP_TRANSPORT=http``) — used when this server is
  deployed as a public HTTPS endpoint (e.g. for Claude mobile / remote
  connectors). OAuth 2.1 is wired in unconditionally via ``auth=`` /
  ``auth_server_provider=`` below; it's simply inert for stdio since FastMCP
  only enforces auth on the HTTP transport's /mcp route.
"""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from ghl_mcp import oauth
from ghl_mcp.tools import register_all

# Public URL this server is reachable at when running over HTTP. Only used
# to build OAuth issuer/resource metadata — irrelevant for stdio.
_public_url = os.environ.get("GHL_MCP_PUBLIC_URL", "https://ghl.devops.australian-cloud.com")
_host = os.environ.get("GHL_MCP_HOST", "127.0.0.1")
_port = int(os.environ.get("GHL_MCP_PORT", "8849"))

# The MCP server. Name follows the skill convention: ``{service}_mcp``.
mcp = FastMCP(
    "gohighlevel_mcp",
    host=_host,
    port=_port,
    auth=oauth.build_auth_settings(_public_url),
    auth_server_provider=oauth.provider,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)

# Wire up every tool.
register_all(mcp)


__all__ = ["mcp"]
