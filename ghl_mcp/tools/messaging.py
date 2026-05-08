"""Messaging tools (4): send SMS, email, WhatsApp; list messages in a thread."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ghl_mcp.client import get_client
from ghl_mcp.formatters import format_response
from ghl_mcp.models import BaseToolInput, PaginationInput, ResponseFormat


class MessagesListInput(PaginationInput):
    conversation_id: str = Field(..., min_length=1)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class SmsSendInput(BaseToolInput):
    contact_id: str = Field(..., min_length=1, description="Recipient contact ID. Get from `ghl_contacts_list`. Contact must have a valid E.164 phone number.")
    message: str = Field(..., min_length=1, max_length=1600, description="SMS body. Standard SMS is 160 chars; longer messages are automatically concatenated (up to 1600 chars).")
    from_number: str | None = Field(default=None, description="Sender E.164 phone number (e.g. +14155551234). Defaults to the location's primary number.")


class EmailSendInput(BaseToolInput):
    contact_id: str = Field(..., min_length=1, description="Recipient contact ID. Get from `ghl_contacts_list`.")
    subject: str = Field(..., min_length=1, max_length=300)
    html: str | None = Field(default=None, max_length=200_000, description="HTML email body. At least one of `html` or `text` is required.")
    text: str | None = Field(default=None, max_length=200_000, description="Plain-text email body. At least one of `html` or `text` is required.")
    from_email: str | None = Field(default=None, description="Sender email address. Defaults to the location's configured sending address.")
    from_name: str | None = Field(default=None, description="Sender display name.")
    attachments: list[str] | None = Field(default=None, description="List of publicly accessible URLs to include as email attachments.")


class WhatsAppSendInput(BaseToolInput):
    contact_id: str = Field(..., min_length=1, description="Recipient contact ID. Get from `ghl_contacts_list`. WhatsApp Business must be configured on the location first.")
    message: str = Field(..., min_length=1, max_length=4000)


def register(mcp) -> None:  # noqa: ANN001
    @mcp.tool(name="ghl_messages_list", annotations={"title": "List messages in conversation", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    async def ghl_messages_list(params: MessagesListInput) -> str:
        """List messages in a conversation thread."""
        client = await get_client()
        result = await client.get(
            f"/conversations/{params.conversation_id}/messages",
            params={"limit": params.limit, "skip": params.skip},
        )
        return format_response(result, params.response_format)

    @mcp.tool(name="ghl_messages_send_sms", annotations={"title": "Send SMS", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
    async def ghl_messages_send_sms(params: SmsSendInput) -> str:
        """Send an SMS to a contact. Charges against the location's wallet at standard markup."""
        client = await get_client()
        body: dict[str, Any] = {"type": "SMS", "contactId": params.contact_id, "message": params.message}
        if params.from_number: body["fromNumber"] = params.from_number
        result = await client.post("/conversations/messages", json=body)
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(name="ghl_messages_send_email", annotations={"title": "Send email", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
    async def ghl_messages_send_email(params: EmailSendInput) -> str:
        """Send a transactional email to a contact. Provide ``html``, ``text``, or both."""
        if not params.html and not params.text:
            return "Error: must provide at least one of `html` or `text`."
        client = await get_client()
        body: dict[str, Any] = {"type": "Email", "contactId": params.contact_id, "subject": params.subject}
        if params.html: body["html"] = params.html
        if params.text: body["text"] = params.text
        if params.from_email: body["emailFrom"] = params.from_email
        if params.from_name: body["fromName"] = params.from_name
        if params.attachments: body["attachments"] = params.attachments
        result = await client.post("/conversations/messages", json=body)
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(name="ghl_messages_send_whatsapp", annotations={"title": "Send WhatsApp message", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
    async def ghl_messages_send_whatsapp(params: WhatsAppSendInput) -> str:
        """Send a WhatsApp message to a contact (requires WhatsApp Business setup on the location)."""
        client = await get_client()
        result = await client.post(
            "/conversations/messages",
            json={"type": "WhatsApp", "contactId": params.contact_id, "message": params.message},
        )
        return format_response(result, ResponseFormat.JSON)
