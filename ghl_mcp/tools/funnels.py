"""Funnel tools (2).

GHL funnels (landing-page and sales-funnel sequences) are read-only via the
API — building them happens in the funnel builder UI. This module exposes
listing funnels and retrieving their pages.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ghl_mcp.client import get_client
from ghl_mcp.config import settings
from ghl_mcp.formatters import format_response, md_table
from ghl_mcp.models import ByIdInput, LocationScopedInput


class FunnelsListInput(LocationScopedInput):
    type: str | None = Field(default=None, description="Filter by funnel type, e.g. 'classic' or 'membership'.")
    category: str | None = Field(default=None)


class FunnelPagesInput(ByIdInput):
    funnel_id: str = Field(..., min_length=1)


def _render_funnels(payload: dict[str, Any]) -> str:
    funnels = payload.get("funnels", [])
    rows = [{
        "id": f.get("_id") or f.get("id"),
        "name": f.get("name"),
        "type": f.get("type", ""),
        "domain": f.get("domain", "") if isinstance(f.get("domain"), str) else "",
    } for f in funnels]
    return md_table(rows, columns=[
        ("id", "ID"), ("name", "Name"), ("type", "Type"), ("domain", "Domain"),
    ])


def _render_pages(payload: dict[str, Any]) -> str:
    pages = payload.get("funnelPages", payload.get("pages", []))
    rows = [{
        "id": p.get("_id") or p.get("id"),
        "name": p.get("name"),
        "step": p.get("stepId", ""),
        "url": p.get("pathname", p.get("url", "")),
    } for p in pages]
    return md_table(rows, columns=[
        ("id", "ID"), ("name", "Page name"), ("step", "Step"), ("url", "URL path"),
    ])


def register(mcp) -> None:  # noqa: ANN001
    @mcp.tool(name="ghl_funnels_list", annotations={"title": "List funnels", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    async def ghl_funnels_list(params: FunnelsListInput) -> str:
        """List all funnels on a location."""
        client = await get_client()
        account = settings.resolve_client(params.location_id)
        api_params: dict[str, Any] = {"locationId": account.location_id}
        if params.type: api_params["type"] = params.type
        if params.category: api_params["category"] = params.category
        result = await client.get("/funnels/funnel/list", params=api_params, location_id=account.location_id)
        return format_response(result, params.response_format, markdown_renderer=_render_funnels)

    @mcp.tool(name="ghl_funnels_get_pages", annotations={"title": "List funnel pages", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    async def ghl_funnels_get_pages(params: FunnelPagesInput) -> str:
        """List all pages within a specific funnel."""
        client = await get_client()
        result = await client.get(f"/funnels/page", params={"funnelId": params.funnel_id}, location_id=params.location_id)
        return format_response(result, params.response_format, markdown_renderer=_render_pages)
