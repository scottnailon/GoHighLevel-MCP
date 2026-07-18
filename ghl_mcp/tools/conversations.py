"""Conversation tools (4)."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ghl_mcp.client import get_client
from ghl_mcp.config import settings
from ghl_mcp.formatters import format_response
from ghl_mcp.models import ByIdInput, LocationScopedInput, PaginationInput, ResponseFormat


class ConversationsListInput(LocationScopedInput, PaginationInput):
    contact_id: str | None = Field(default=None)
    assigned_to: str | None = Field(default=None)
    starred: bool | None = Field(default=None)


class ConversationGetInput(ByIdInput):
    conversation_id: str = Field(..., min_length=1)


class ConversationCreateInput(LocationScopedInput):
    contact_id: str = Field(..., min_length=1)


class ConversationSearchInput(LocationScopedInput, PaginationInput):
    query: str = Field(..., min_length=1, max_length=200)


def register(mcp) -> None:  # noqa: ANN001
    @mcp.tool(name="ghl_conversations_list", annotations={"title": "List conversations", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    async def ghl_conversations_list(params: ConversationsListInput) -> str:
        """List conversations in a location, optionally filtered by contact or assignee."""
        client = await get_client()
        account = settings.resolve_client(params.location_id)
        # /conversations/search has no "skip" param — only a startAfterDate
        # cursor, which we don't track across stateless calls. Omit it
        # rather than send an unsupported param (GHL rejects unknown params).
        api_params: dict[str, Any] = {"locationId": account.location_id, "limit": params.limit}
        if params.contact_id: api_params["contactId"] = params.contact_id
        if params.assigned_to: api_params["assignedTo"] = params.assigned_to
        if params.starred is not None: api_params["starred"] = "true" if params.starred else "false"
        result = await client.get("/conversations/search", params=api_params, location_id=account.location_id)
        return format_response(result, params.response_format)

    @mcp.tool(name="ghl_conversations_get", annotations={"title": "Get conversation", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    async def ghl_conversations_get(params: ConversationGetInput) -> str:
        """Get full details of a single conversation including the message thread metadata."""
        client = await get_client()
        result = await client.get(f"/conversations/{params.conversation_id}", location_id=params.location_id)
        return format_response(result, params.response_format)

    @mcp.tool(name="ghl_conversations_create", annotations={"title": "Create conversation", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
    async def ghl_conversations_create(params: ConversationCreateInput) -> str:
        """Create a new conversation thread for a contact."""
        client = await get_client()
        account = settings.resolve_client(params.location_id)
        result = await client.post(
            "/conversations/",
            json={"locationId": account.location_id, "contactId": params.contact_id},
            location_id=account.location_id,
        )
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(name="ghl_conversations_search", annotations={"title": "Search conversations", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    async def ghl_conversations_search(params: ConversationSearchInput) -> str:
        """Free-text search across conversation messages."""
        client = await get_client()
        account = settings.resolve_client(params.location_id)
        result = await client.get(
            "/conversations/search",
            params={"locationId": account.location_id, "query": params.query, "limit": params.limit},
            location_id=account.location_id,
        )
        return format_response(result, params.response_format)
