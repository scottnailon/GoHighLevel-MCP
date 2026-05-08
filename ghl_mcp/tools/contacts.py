"""Contact management tools (12).

Covers the full lifecycle: list/search, get, create, update, delete, upsert,
plus tag and note management. Mirrors the GHL Contacts V2 API surface.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import Field, field_validator

from ghl_mcp.client import get_client
from ghl_mcp.config import settings
from ghl_mcp.formatters import (
    fmt_custom_fields_summary,
    fmt_date,
    format_response,
    md_pagination_footer,
    md_table,
)
from ghl_mcp.models import BaseToolInput, LocationScopedInput, PaginationInput, ResponseFormat
from ghl_mcp.pagination import build_pagination_response, extract_total


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


class ContactsListInput(LocationScopedInput, PaginationInput):
    """Input for listing/searching contacts."""

    query: str | None = Field(
        default=None,
        description="Free-text search across name, email, and phone.",
        max_length=200,
    )
    tags: list[str] | None = Field(
        default=None,
        description="Filter to contacts having ALL of these tag names.",
        max_length=20,
    )


class ContactGetInput(BaseToolInput):
    contact_id: str = Field(..., description="The GHL contact ID.", min_length=1)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


_E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def _validate_phone(v: str | None) -> str | None:
    if v is not None and not _E164_RE.match(v):
        raise ValueError("Phone must be in E.164 format (e.g. +61412345678)")
    return v


class ContactCreateInput(LocationScopedInput):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(
        default=None,
        description="E.164 format required, e.g. +61412345678 or +14155551234. Country code must be included.",
        max_length=30,
    )
    tags: list[str] | None = Field(
        default=None,
        description="List of tag strings to apply at creation. Tags are created automatically if they don't exist.",
        max_length=50,
    )
    source: str | None = Field(
        default=None,
        description="How this contact was acquired. Common values: 'website-form', 'manual', 'import', 'API', 'facebook', 'google'. Any string is accepted.",
        max_length=100,
    )
    dnd: bool | None = Field(
        default=None,
        description="Do Not Disturb flag. When True, disables ALL outbound messaging channels unless dnd_settings overrides specific channels.",
    )
    custom_fields: dict[str, Any] | None = Field(
        default=None,
        description="Custom field values keyed by field ID (not name). Call `ghl_custom_fields_list` first to discover field IDs. Example: `{'abc123fieldId': 'value'}`",
    )
    address1: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, description="ISO 2-letter country code (e.g. 'AU', 'US', 'GB').", max_length=2)

    @field_validator("phone", mode="after")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return _validate_phone(v)


class ContactUpdateInput(BaseToolInput):
    contact_id: str = Field(..., min_length=1, description="The GHL contact ID. Get from `ghl_contacts_list` or `ghl_contacts_upsert`.")
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(
        default=None,
        description="E.164 format required, e.g. +61412345678 or +14155551234. Country code must be included.",
        max_length=30,
    )
    tags: list[str] | None = Field(
        default=None,
        description="Replaces all existing tags. List of tag strings; tags are created automatically if they don't exist.",
        max_length=50,
    )
    dnd: bool | None = Field(
        default=None,
        description="Do Not Disturb flag. When True, disables ALL outbound messaging channels unless dnd_settings overrides specific channels.",
    )
    custom_fields: dict[str, Any] | None = Field(
        default=None,
        description="Custom field values keyed by field ID (not name). Call `ghl_custom_fields_list` first to discover field IDs. Example: `{'abc123fieldId': 'value'}`",
    )
    address1: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, description="ISO 2-letter country code (e.g. 'AU', 'US', 'GB').", max_length=2)

    @field_validator("phone", mode="after")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return _validate_phone(v)


class ContactIdInput(BaseToolInput):
    contact_id: str = Field(..., min_length=1)


class ContactUpsertInput(ContactCreateInput):
    """Same shape as create — GHL deduplicates on email/phone."""


class ContactTagsInput(BaseToolInput):
    contact_id: str = Field(..., min_length=1, description="The GHL contact ID. Get from `ghl_contacts_list` or `ghl_contacts_upsert`.")
    tags: list[str] = Field(..., min_length=1, max_length=50, description="List of tag strings. Tags are created automatically if they don't exist.")


class ContactNoteCreateInput(BaseToolInput):
    contact_id: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1, max_length=5000)
    user_id: str | None = Field(default=None, description="The GHL user ID to attribute the note to.")


class ContactTaskCreateInput(BaseToolInput):
    contact_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=200)
    body: str | None = Field(default=None, max_length=5000)
    due_date: str | None = Field(
        default=None,
        description="ISO 8601 datetime (e.g. '2026-05-15T14:00:00Z'). If omitted, no due date is set.",
    )
    assigned_to: str | None = Field(default=None, description="GHL user ID to assign the task to.")


# ---------------------------------------------------------------------------
# Markdown renderers
# ---------------------------------------------------------------------------


def _owner_label(c: dict[str, Any]) -> str:
    """Return the best available owner label from a contact dict."""
    # GHL may return an assignedTo sub-object or just a string ID.
    assigned = c.get("assignedTo")
    if isinstance(assigned, dict):
        name = (
            f"{assigned.get('firstName', '')} {assigned.get('lastName', '')}".strip()
            or assigned.get("name", "")
            or assigned.get("email", "")
            or assigned.get("id", "")
        )
        return name
    if isinstance(assigned, str) and assigned:
        return assigned  # ID only — better than nothing
    return ""


def _render_contact_list(payload: dict[str, Any]) -> str:
    contacts = payload.get("contacts", [])
    lines: list[str] = []

    # Build table rows — one row per contact.
    rows = []
    custom_summaries: dict[int, str] = {}
    for idx, c in enumerate(contacts):
        dnd = "DND" if c.get("dnd") else ""
        rows.append({
            "id": c.get("id", ""),
            "name": _full_name(c),
            "email": c.get("email", ""),
            "phone": c.get("phone", ""),
            "tags": c.get("tags", []),
            "source": c.get("source", ""),
            "owner": _owner_label(c),
            "dnd": dnd,
            "created": fmt_date(c.get("dateAdded")),
        })
        cf_summary = fmt_custom_fields_summary(c.get("customFields"))
        if cf_summary:
            custom_summaries[idx] = cf_summary

    table_lines = md_table(
        rows,
        columns=[
            ("id", "ID"),
            ("name", "Name"),
            ("email", "Email"),
            ("phone", "Phone"),
            ("tags", "Tags"),
            ("source", "Source"),
            ("owner", "Owner"),
            ("dnd", "DND"),
            ("created", "Created"),
        ],
    ).splitlines()

    # If we have custom field summaries, interleave them after each data row.
    # table_lines[0] = header, [1] = separator, [2+] = data rows.
    if custom_summaries:
        header_lines = table_lines[:2]
        data_lines = table_lines[2:]
        new_data_lines: list[str] = []
        for idx, row_line in enumerate(data_lines):
            new_data_lines.append(row_line)
            if idx in custom_summaries:
                new_data_lines.append(f"  ↳ Custom: {custom_summaries[idx]}")
        lines.extend(header_lines)
        lines.extend(new_data_lines)
    else:
        lines.extend(table_lines)

    footer = md_pagination_footer(
        count=payload["count"],
        total=payload["total"],
        skip=payload["skip"],
        limit=payload["limit"],
        has_more=payload["has_more"],
        next_skip=payload["next_skip"],
        pagination_note=payload.get("pagination_note"),
    )
    lines.append("")
    lines.append(footer)
    return "\n".join(lines)


def _render_contact_detail(c: dict[str, Any]) -> str:
    name = _full_name(c) or "(no name)"
    tags = ", ".join(c.get("tags", [])) or "_none_"
    owner = _owner_label(c) or "_unassigned_"
    dnd_flag = "  **[DND]**" if c.get("dnd") else ""

    # Address — only show line if at least one component present.
    addr_parts = [c.get("city", ""), c.get("state", ""), c.get("country", "")]
    address_line = ", ".join(p for p in addr_parts if p)

    lines = [
        f"## Contact: {name}{dnd_flag}",
        "",
        f"**Email:** {c.get('email') or '_none_'}  "
        f"**Phone:** {c.get('phone') or '_none_'}  "
        f"**Tags:** {tags}",
        f"**Source:** {c.get('source') or '_unknown_'}  "
        f"**Owner:** {owner}  "
        f"**Created:** {c.get('dateAdded') or '_unknown_'}",
    ]
    if address_line:
        lines.append(f"**Address:** {address_line}")

    custom_fields = c.get("customFields") or []
    if custom_fields:
        lines.append("")
        lines.append("### Custom Fields")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|---|---|")
        for cf in custom_fields:
            field_name = (
                cf.get("fieldKey")
                or cf.get("name")
                or cf.get("id")
                or "?"
            )
            value = cf.get("value")
            if value is None:
                value = ""
            lines.append(f"| {str(field_name).replace('|', r'\|')} | {str(value).replace('|', r'\|')} |")

    return "\n".join(lines)


def _full_name(c: dict[str, Any]) -> str:
    parts = [c.get("firstName", ""), c.get("lastName", "")]
    return " ".join(p for p in parts if p).strip() or c.get("contactName", "")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register(mcp) -> None:  # noqa: ANN001
    """Register all contact tools with the MCP server."""

    @mcp.tool(
        name="ghl_contacts_list",
        annotations={
            "title": "List contacts",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ghl_contacts_list(params: ContactsListInput) -> str:
        """List or search contacts in a GHL location.

        Returns paginated results with name, email, phone, tags, and created
        date for each contact. Use the ``query`` parameter for free-text
        search across name/email/phone, or ``tags`` to filter to contacts
        having ALL specified tags.

        Pagination: pass ``skip`` and ``limit``. The response includes
        ``next_skip`` for fetching the next page.
        """
        client = await get_client()
        location_id = settings.require_location_id(params.location_id)
        result = await client.get(
            "/contacts/",
            params={
                "locationId": location_id,
                "limit": params.limit,
                "skip": params.skip,
                "query": params.query,
                "tags": ",".join(params.tags) if params.tags else None,
            },
        )
        contacts = result.get("contacts", [])
        page = build_pagination_response(
            contacts,
            total=extract_total(result, "total"),
            limit=params.limit,
            skip=params.skip,
            items_key="contacts",
        )
        return format_response(page, params.response_format, markdown_renderer=_render_contact_list)

    @mcp.tool(
        name="ghl_contacts_get",
        annotations={
            "title": "Get contact",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ghl_contacts_get(params: ContactGetInput) -> str:
        """Get full details for a single contact by ID, including custom field values."""
        client = await get_client()
        result = await client.get(f"/contacts/{params.contact_id}")
        contact = result.get("contact", result)
        return format_response(contact, params.response_format, markdown_renderer=_render_contact_detail)

    @mcp.tool(
        name="ghl_contacts_create",
        annotations={
            "title": "Create contact",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def ghl_contacts_create(params: ContactCreateInput) -> str:
        """Create a new contact in a GHL location.

        Returns the newly-created contact including its assigned ID. Note: if a
        contact with the same email or phone already exists, this will create
        a duplicate. Use ``ghl_contacts_upsert`` if you want dedup-by-email.
        """
        client = await get_client()
        location_id = settings.require_location_id(params.location_id)
        body = _build_contact_body(params, location_id)
        result = await client.post("/contacts/", json=body)
        return format_response(result, ResponseFormat.MARKDOWN if params.response_format == ResponseFormat.MARKDOWN else params.response_format)

    @mcp.tool(
        name="ghl_contacts_update",
        annotations={
            "title": "Update contact",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ghl_contacts_update(params: ContactUpdateInput) -> str:
        """Update fields on an existing contact. Only fields you pass are modified."""
        client = await get_client()
        body = {k: v for k, v in params.model_dump().items() if v is not None and k != "contact_id"}
        # Convert snake_case to camelCase for GHL.
        body = _to_camel(body)
        result = await client.put(f"/contacts/{params.contact_id}", json=body)
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(
        name="ghl_contacts_delete",
        annotations={
            "title": "Delete contact",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ghl_contacts_delete(params: ContactIdInput) -> str:
        """Delete a contact permanently. This cannot be undone."""
        client = await get_client()
        await client.delete(f"/contacts/{params.contact_id}")
        return f"Contact {params.contact_id} deleted."

    @mcp.tool(
        name="ghl_contacts_upsert",
        annotations={
            "title": "Create or update contact (upsert)",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ghl_contacts_upsert(params: ContactUpsertInput) -> str:
        """Create or update a contact, deduplicated by email or phone.

        If a contact with the same email or phone already exists, that
        existing contact is updated. Otherwise a new one is created.
        Recommended over ``ghl_contacts_create`` when importing CSV data.
        """
        client = await get_client()
        location_id = settings.require_location_id(params.location_id)
        body = _build_contact_body(params, location_id)
        result = await client.post("/contacts/upsert", json=body)
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(
        name="ghl_contacts_add_tags",
        annotations={
            "title": "Add tags to contact",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ghl_contacts_add_tags(params: ContactTagsInput) -> str:
        """Add one or more tags to a contact. Idempotent — duplicate tags are ignored by GHL."""
        client = await get_client()
        result = await client.post(
            f"/contacts/{params.contact_id}/tags",
            json={"tags": params.tags},
        )
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(
        name="ghl_contacts_remove_tags",
        annotations={
            "title": "Remove tags from contact",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ghl_contacts_remove_tags(params: ContactTagsInput) -> str:
        """Remove one or more tags from a contact."""
        client = await get_client()
        result = await client.delete(
            f"/contacts/{params.contact_id}/tags",
            extra_headers=None,
            json={"tags": params.tags},
        )
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(
        name="ghl_contacts_add_note",
        annotations={
            "title": "Add note to contact",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def ghl_contacts_add_note(params: ContactNoteCreateInput) -> str:
        """Append a note to a contact's record. Useful for logging call outcomes, observations, follow-ups."""
        client = await get_client()
        body: dict[str, Any] = {"body": params.body}
        if params.user_id:
            body["userId"] = params.user_id
        result = await client.post(f"/contacts/{params.contact_id}/notes", json=body)
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(
        name="ghl_contacts_get_notes",
        annotations={
            "title": "List contact notes",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ghl_contacts_get_notes(params: ContactIdInput) -> str:
        """Retrieve all notes attached to a contact, newest first."""
        client = await get_client()
        result = await client.get(f"/contacts/{params.contact_id}/notes")
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(
        name="ghl_contacts_add_task",
        annotations={
            "title": "Create task for contact",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def ghl_contacts_add_task(params: ContactTaskCreateInput) -> str:
        """Create a task associated with a contact (e.g. "Follow up Tuesday")."""
        client = await get_client()
        body: dict[str, Any] = {"title": params.title}
        if params.body:
            body["body"] = params.body
        if params.due_date:
            body["dueDate"] = params.due_date
        if params.assigned_to:
            body["assignedTo"] = params.assigned_to
        result = await client.post(f"/contacts/{params.contact_id}/tasks", json=body)
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(
        name="ghl_contacts_get_tasks",
        annotations={
            "title": "List contact tasks",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ghl_contacts_get_tasks(params: ContactIdInput) -> str:
        """Retrieve all tasks for a contact (open and completed)."""
        client = await get_client()
        result = await client.get(f"/contacts/{params.contact_id}/tasks")
        return format_response(result, ResponseFormat.JSON)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_contact_body(params: BaseToolInput, location_id: str) -> dict[str, Any]:
    """Translate a Pydantic contact-create/update model to GHL's camelCase body."""
    payload = params.model_dump(exclude_none=True)
    # Strip MCP-specific fields that aren't part of GHL's payload.
    for k in ("location_id", "response_format"):
        payload.pop(k, None)
    body = _to_camel(payload)
    body["locationId"] = location_id
    return body


_SNAKE_TO_CAMEL = {
    "first_name": "firstName",
    "last_name": "lastName",
    "postal_code": "postalCode",
    "custom_fields": "customFields",
    "user_id": "userId",
    "due_date": "dueDate",
    "assigned_to": "assignedTo",
    "contact_id": "contactId",
}


def _to_camel(d: dict[str, Any]) -> dict[str, Any]:
    """Convert a snake_case-keyed dict to GHL's camelCase keys."""
    return {_SNAKE_TO_CAMEL.get(k, k): v for k, v in d.items()}
