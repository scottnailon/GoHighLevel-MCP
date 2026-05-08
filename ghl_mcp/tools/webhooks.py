"""Webhook tools (4).

GHL webhooks deliver real-time event notifications to your endpoints.
Critical for any external system that needs to react to GHL events
(form submissions, contact updates, opportunity stage changes, etc.).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from ghl_mcp.client import get_client
from ghl_mcp.config import settings
from ghl_mcp.formatters import format_response, md_table
from ghl_mcp.models import BaseToolInput, LocationScopedInput, ResponseFormat

# Valid GHL webhook event names (sourced from GHL Webhooks documentation).
WebhookEvent = Literal[
    "ContactCreate", "ContactUpdate", "ContactDelete", "ContactDndUpdate", "ContactTagUpdate",
    "NoteCreate", "NoteUpdate", "NoteDelete",
    "TaskCreate", "TaskUpdate", "TaskDelete",
    "AppointmentCreate", "AppointmentUpdate", "AppointmentDelete",
    "OpportunityCreate", "OpportunityUpdate", "OpportunityDelete",
    "OpportunityStageUpdate", "OpportunityStatusUpdate",
    "ConversationCreate", "ConversationUpdate",
    "InboundMessage", "OutboundMessage",
    "FormSubmission", "SurveySubmission",
    "OrderCreate", "OrderStatusUpdate",
    "InvoiceCreate", "InvoiceUpdate", "InvoiceSend", "InvoiceDelete",
    "PaymentReceived",
]


class WebhooksListInput(LocationScopedInput):
    pass


class WebhookCreateInput(LocationScopedInput):
    url: str = Field(..., min_length=1, max_length=2000, description="HTTPS endpoint that will receive POST requests. Must be publicly accessible and respond 2xx within 10s.")
    events: list[WebhookEvent] = Field(
        ...,
        min_length=1,
        description=(
            "List of event types to subscribe to. Valid values include: "
            "ContactCreate, ContactUpdate, ContactDelete, ContactDndUpdate, ContactTagUpdate, "
            "AppointmentCreate, AppointmentUpdate, AppointmentDelete, "
            "OpportunityCreate, OpportunityUpdate, OpportunityDelete, OpportunityStageUpdate, OpportunityStatusUpdate, "
            "ConversationCreate, ConversationUpdate, InboundMessage, OutboundMessage, "
            "FormSubmission, SurveySubmission, NoteCreate, TaskCreate, "
            "OrderCreate, InvoiceCreate, PaymentReceived. See WebhookEvent type for full list."
        ),
    )
    name: str | None = Field(default=None, max_length=200, description="Friendly name for tracking this webhook subscription.")


class WebhookUpdateInput(BaseToolInput):
    webhook_id: str = Field(..., min_length=1)
    url: str | None = Field(default=None, max_length=2000, description="New HTTPS endpoint URL.")
    events: list[WebhookEvent] | None = Field(default=None, description="Replaces the full event list. See WebhookCreateInput.events for valid values.")
    name: str | None = Field(default=None, max_length=200)
    enabled: bool | None = Field(default=None, description="Set False to pause deliveries without deleting the webhook.")


class WebhookDeleteInput(BaseToolInput):
    webhook_id: str = Field(..., min_length=1)


def _render_webhooks(payload: dict[str, Any]) -> str:
    hooks = payload.get("webhooks", payload.get("hooks", []))
    rows = [{
        "id": h.get("id"),
        "name": h.get("name", ""),
        "url": h.get("url", "")[:60],
        "events": h.get("events", []),
        "enabled": h.get("enabled", True),
    } for h in hooks]
    return md_table(rows, columns=[
        ("id", "ID"), ("name", "Name"), ("url", "URL"),
        ("events", "Events"), ("enabled", "Enabled"),
    ])


def register(mcp) -> None:  # noqa: ANN001
    @mcp.tool(name="ghl_webhooks_list", annotations={"title": "List webhooks", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    async def ghl_webhooks_list(params: WebhooksListInput) -> str:
        """List all webhooks configured for a location."""
        client = await get_client()
        location_id = settings.require_location_id(params.location_id)
        result = await client.get("/hooks/", params={"locationId": location_id})
        return format_response(result, params.response_format, markdown_renderer=_render_webhooks)

    @mcp.tool(name="ghl_webhooks_create", annotations={"title": "Create webhook", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
    async def ghl_webhooks_create(params: WebhookCreateInput) -> str:
        """Create a new webhook subscription.

        GHL will POST event payloads to ``url`` whenever any of the subscribed
        events fire. The endpoint should respond 2xx within 10s.
        """
        client = await get_client()
        location_id = settings.require_location_id(params.location_id)
        body: dict[str, Any] = {
            "locationId": location_id,
            "url": params.url,
            "events": params.events,
        }
        if params.name: body["name"] = params.name
        result = await client.post("/hooks/", json=body)
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(name="ghl_webhooks_update", annotations={"title": "Update webhook", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    async def ghl_webhooks_update(params: WebhookUpdateInput) -> str:
        """Update a webhook's URL, events, name, or enabled state."""
        client = await get_client()
        body: dict[str, Any] = {}
        if params.url is not None: body["url"] = params.url
        if params.events is not None: body["events"] = params.events
        if params.name is not None: body["name"] = params.name
        if params.enabled is not None: body["enabled"] = params.enabled
        if not body: return "No fields to update."
        result = await client.put(f"/hooks/{params.webhook_id}", json=body)
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(name="ghl_webhooks_delete", annotations={"title": "Delete webhook", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": True})
    async def ghl_webhooks_delete(params: WebhookDeleteInput) -> str:
        """Delete a webhook subscription. Stops all further event deliveries to the URL."""
        client = await get_client()
        await client.delete(f"/hooks/{params.webhook_id}")
        return f"Webhook {params.webhook_id} deleted."
