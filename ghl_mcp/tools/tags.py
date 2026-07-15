"""Tag tools (1).

GHL tags are simple string labels created on-the-fly via contact endpoints. There
is no top-level create/update/delete API — tags are created the moment they're
applied to a contact (via ``ghl_contacts_add_tags``). This module exposes only
listing.
"""

from __future__ import annotations

from typing import Any

from ghl_mcp.client import get_client
from ghl_mcp.config import settings
from ghl_mcp.formatters import format_response, md_table
from ghl_mcp.models import LocationScopedInput


class TagsListInput(LocationScopedInput):
    pass


def _render_tag_list(payload: dict[str, Any]) -> str:
    tags = payload.get("tags", [])
    rows = [{"id": t.get("id"), "name": t.get("name")} for t in tags]
    return md_table(rows, columns=[("id", "ID"), ("name", "Tag name")])


def register(mcp) -> None:  # noqa: ANN001
    @mcp.tool(name="ghl_tags_list", annotations={"title": "List tags", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    async def ghl_tags_list(params: TagsListInput) -> str:
        """List all tags currently in use on a location."""
        client = await get_client()
        account = settings.resolve_client(params.location_id)
        result = await client.get(f"/locations/{account.location_id}/tags", location_id=account.location_id)
        return format_response(result, params.response_format, markdown_renderer=_render_tag_list)
