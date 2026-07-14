"""Smoke test: every package module imports without error.

This catches:
- syntax errors
- missing imports
- circular dependencies
- typos in @mcp.tool decorators

Run with: ``pytest tests/test_imports.py -v``
"""

from __future__ import annotations

import importlib

import pytest

PACKAGE_MODULES = [
    "ghl_mcp",
    "ghl_mcp.config",
    "ghl_mcp.errors",
    "ghl_mcp.client",
    "ghl_mcp.models",
    "ghl_mcp.pagination",
    "ghl_mcp.formatters",
    "ghl_mcp.server",
]

TOOL_MODULES = [
    "ghl_mcp.tools",
    "ghl_mcp.tools.contacts",
    "ghl_mcp.tools.conversations",
    "ghl_mcp.tools.messaging",
    "ghl_mcp.tools.calendars",
    "ghl_mcp.tools.appointments",
    "ghl_mcp.tools.pipelines",
    "ghl_mcp.tools.opportunities",
    "ghl_mcp.tools.custom_fields",
    "ghl_mcp.tools.tags",
    "ghl_mcp.tools.users",
    "ghl_mcp.tools.workflows",
    "ghl_mcp.tools.forms",
    "ghl_mcp.tools.funnels",
]


@pytest.mark.parametrize("module_name", PACKAGE_MODULES + TOOL_MODULES)
def test_module_imports(module_name: str) -> None:
    """Every listed module imports cleanly."""
    mod = importlib.import_module(module_name)
    assert mod is not None, f"Module {module_name} imported as None"


def test_tools_register_function() -> None:
    """Every tool module exposes a callable ``register`` function."""
    from ghl_mcp.tools import (
        appointments, calendars, contacts, conversations,
        custom_fields, forms, funnels, messaging, opportunities,
        pipelines, tags, users, workflows,
    )
    modules = [
        appointments, calendars, contacts, conversations,
        custom_fields, forms, funnels, messaging, opportunities,
        pipelines, tags, users, workflows,
    ]
    for mod in modules:
        assert hasattr(mod, "register"), f"{mod.__name__} missing `register`"
        assert callable(mod.register), f"{mod.__name__}.register is not callable"


def test_no_agency_only_tool_leaked_in() -> None:
    """Agency-scoped modules (cross-location listing, sub-account lifecycle,
    SaaS billing, snapshots, webhooks) must never be present in this
    client-facing build — they live in a separate, private repo."""
    from ghl_mcp.tools import __all__ as registered

    forbidden = {"locations", "companies", "saas", "snapshots", "webhooks"}
    assert not (set(registered) & forbidden), (
        f"Agency-only module leaked into the client build: {set(registered) & forbidden}"
    )


def test_server_is_fastmcp() -> None:
    """The exported ``mcp`` is a FastMCP instance."""
    from mcp.server.fastmcp import FastMCP

    from ghl_mcp.server import mcp
    assert isinstance(mcp, FastMCP)


def test_server_name_follows_convention() -> None:
    """Server name follows the {service}_mcp pattern."""
    from ghl_mcp.server import mcp
    assert mcp.name == "gohighlevel_mcp"
