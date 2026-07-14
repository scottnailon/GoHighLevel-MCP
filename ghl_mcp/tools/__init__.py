"""Tool modules. Each module exposes a ``register(mcp)`` function that
registers its tools with the FastMCP server.

This is the client-facing build — every tool here operates on a single
sub-account (the one identified by GHL_LOCATION_ID). Cross-location listing,
sub-account lifecycle, SaaS billing, snapshots, and webhook management are
agency-only concerns and live in a separate, private repo — never here.
"""

from ghl_mcp.tools import (
    appointments,
    calendars,
    contacts,
    conversations,
    custom_fields,
    forms,
    funnels,
    messaging,
    opportunities,
    pipelines,
    tags,
    users,
    workflows,
)

__all__ = [
    "appointments",
    "calendars",
    "contacts",
    "conversations",
    "custom_fields",
    "forms",
    "funnels",
    "messaging",
    "opportunities",
    "pipelines",
    "tags",
    "users",
    "workflows",
]


def register_all(mcp) -> None:
    """Register every tool from every module with the given MCP server."""
    for module in (
        contacts, conversations, messaging, calendars, appointments,
        pipelines, opportunities, custom_fields, tags, users, workflows,
        forms, funnels,
    ):
        module.register(mcp)
