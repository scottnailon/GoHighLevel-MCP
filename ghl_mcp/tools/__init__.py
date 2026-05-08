"""Tool modules. Each module exposes a ``register(mcp)`` function that
registers its tools with the FastMCP server."""

from ghl_mcp.tools import (
    appointments,
    calendars,
    companies,
    contacts,
    conversations,
    custom_fields,
    forms,
    funnels,
    locations,
    messaging,
    opportunities,
    pipelines,
    saas,
    snapshots,
    tags,
    users,
    webhooks,
    workflows,
)

__all__ = [
    "appointments",
    "calendars",
    "companies",
    "contacts",
    "conversations",
    "custom_fields",
    "forms",
    "funnels",
    "locations",
    "messaging",
    "opportunities",
    "pipelines",
    "saas",
    "snapshots",
    "tags",
    "users",
    "webhooks",
    "workflows",
]


def register_all(mcp) -> None:
    """Register every tool from every module with the given MCP server."""
    for module in (
        contacts, conversations, messaging, calendars, appointments,
        pipelines, opportunities, custom_fields, tags, users, workflows,
        forms, snapshots, locations, webhooks, funnels, companies, saas,
    ):
        module.register(mcp)
