"""Opportunity tools (8). Deals within sales pipelines."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from ghl_mcp.client import get_client
from ghl_mcp.config import settings
from ghl_mcp.formatters import (
    fmt_currency,
    fmt_date,
    format_response,
    md_pagination_footer,
    md_table,
)
from ghl_mcp.models import ByIdInput, LocationScopedInput, PaginationInput, ResponseFormat
from ghl_mcp.pagination import build_pagination_response, extract_total


class OppStatus(str, Enum):
    OPEN = "open"
    WON = "won"
    LOST = "lost"
    ABANDONED = "abandoned"


class OpportunitiesListInput(LocationScopedInput, PaginationInput):
    pipeline_id: str | None = Field(default=None, description="Filter to a specific pipeline. Get pipeline IDs from `ghl_pipelines_list`.")
    pipeline_stage_id: str | None = Field(default=None, description="Filter to a specific stage. Get stage IDs from `ghl_pipelines_get`.")
    status: OppStatus | None = Field(default=None, description="Filter by status. Valid values: open, won, lost, abandoned.")
    contact_id: str | None = Field(default=None, description="Filter to opps for a specific contact. Get from `ghl_contacts_list`.")
    assigned_to: str | None = Field(default=None, description="Filter to opps assigned to a user. Get user IDs from `ghl_users_list`.")
    query: str | None = Field(default=None, max_length=200, description="Free-text search across opportunity name.")


class OpportunityGetInput(ByIdInput):
    opportunity_id: str = Field(..., min_length=1)


class OpportunityCreateInput(LocationScopedInput):
    pipeline_id: str = Field(..., min_length=1, description="Get pipeline IDs from `ghl_pipelines_list`.")
    pipeline_stage_id: str = Field(..., min_length=1, description="Get stage IDs from `ghl_pipelines_get`. Must belong to the specified pipeline.")
    name: str = Field(..., min_length=1, max_length=200)
    contact_id: str = Field(..., min_length=1, description="The GHL contact ID. Get from `ghl_contacts_list` or `ghl_contacts_upsert`.")
    monetary_value: float | None = Field(default=None, ge=0, description="Deal value as a number (e.g. 1500.00). Do not include currency symbols.")
    close_date: str | None = Field(default=None, description="Expected close date as ISO 8601, e.g. '2026-06-30T00:00:00Z'.")
    status: OppStatus = Field(default=OppStatus.OPEN, description="Opportunity status. Valid values: open, won, lost, abandoned.")
    source: str | None = Field(default=None, max_length=200)
    assigned_to: str | None = Field(default=None, description="GHL user ID to assign to. Get from `ghl_users_list`.")
    custom_fields: dict[str, Any] | None = Field(
        default=None,
        description="Custom field values keyed by field ID (not name). Call `ghl_custom_fields_list` with model='opportunity' first to discover field IDs. Example: `{'abc123fieldId': 'value'}`",
    )


class OpportunityUpdateInput(ByIdInput):
    opportunity_id: str = Field(..., min_length=1)
    name: str | None = Field(default=None, max_length=200)
    monetary_value: float | None = Field(default=None, ge=0, description="Deal value as a number (e.g. 1500.00). Do not include currency symbols.")
    close_date: str | None = Field(default=None, description="Expected close date as ISO 8601, e.g. '2026-06-30T00:00:00Z'.")
    pipeline_stage_id: str | None = Field(default=None, description="Get stage IDs from `ghl_pipelines_get`. Must belong to the specified pipeline.")
    status: OppStatus | None = Field(default=None, description="Opportunity status. Valid values: open, won, lost, abandoned.")
    assigned_to: str | None = Field(default=None, description="GHL user ID to assign to. Get from `ghl_users_list`.")
    custom_fields: dict[str, Any] | None = Field(
        default=None,
        description="Custom field values keyed by field ID (not name). Call `ghl_custom_fields_list` with model='opportunity' first to discover field IDs. Example: `{'abc123fieldId': 'value'}`",
    )


class OpportunityIdInput(ByIdInput):
    opportunity_id: str = Field(..., min_length=1)


class OpportunityMoveStageInput(ByIdInput):
    opportunity_id: str = Field(..., min_length=1)
    pipeline_stage_id: str = Field(..., min_length=1, description="Target stage ID. Get stage IDs from `ghl_pipelines_get`.")


class OpportunityUpdateStatusInput(ByIdInput):
    opportunity_id: str = Field(..., min_length=1)
    status: OppStatus = Field(..., description="New status. Valid values: open, won, lost, abandoned.")


def _opp_contact_name(o: dict[str, Any]) -> str:
    """Return the best contact label available on an opportunity dict."""
    # GHL may embed a contact sub-object or just store contactName/contactId.
    contact = o.get("contact")
    if isinstance(contact, dict):
        name = (
            f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip()
            or contact.get("name", "")
            or contact.get("email", "")
        )
        if name:
            return name
    contact_name = o.get("contactName", "")
    if contact_name:
        return contact_name
    return o.get("contactId", "")


def _opp_assigned_name(o: dict[str, Any]) -> str:
    """Return the assigned user label for an opportunity."""
    assigned = o.get("assignedTo")
    if isinstance(assigned, dict):
        return (
            f"{assigned.get('firstName', '')} {assigned.get('lastName', '')}".strip()
            or assigned.get("name", "")
            or assigned.get("email", "")
            or assigned.get("id", "")
        )
    if isinstance(assigned, str) and assigned:
        return assigned
    return ""


def _opp_stage_name(o: dict[str, Any]) -> str:
    """Return the stage display name, falling back to the stage ID."""
    stage = o.get("pipelineStage")
    if isinstance(stage, dict):
        return stage.get("name", "") or o.get("pipelineStageId", "")
    return o.get("pipelineStageName", "") or o.get("pipelineStageId", "")


def _render_opp_list(payload: dict[str, Any]) -> str:
    opps = payload.get("opportunities", [])
    rows = []
    for o in opps:
        rows.append({
            "id": o.get("id", ""),
            "name": o.get("name", ""),
            "value": fmt_currency(o.get("monetaryValue")),
            "status": o.get("status", ""),
            "stage": _opp_stage_name(o),
            "contact": _opp_contact_name(o),
            "assigned": _opp_assigned_name(o),
            "close_date": fmt_date(o.get("closeDate")),
        })
    table = md_table(rows, columns=[
        ("id", "ID"), ("name", "Name"), ("value", "Value"),
        ("status", "Status"), ("stage", "Stage"), ("contact", "Contact"),
        ("assigned", "Assigned"), ("close_date", "Close Date"),
    ])
    footer = md_pagination_footer(
        count=payload["count"], total=payload["total"], skip=payload["skip"],
        limit=payload["limit"], has_more=payload["has_more"], next_skip=payload["next_skip"],
        pagination_note=payload.get("pagination_note"),
    )
    return f"{table}\n\n{footer}"


def _render_opp_detail(o: dict[str, Any]) -> str:
    """Card layout for a single opportunity detail view."""
    # GHL wraps the opp in an "opportunity" key for get-by-id.
    opp = o.get("opportunity", o)

    pipeline_name = ""
    pipeline = opp.get("pipeline")
    if isinstance(pipeline, dict):
        pipeline_name = pipeline.get("name", "")
    pipeline_name = pipeline_name or opp.get("pipelineId", "")

    stage_name = _opp_stage_name(opp)
    status = opp.get("status", "")
    value = fmt_currency(opp.get("monetaryValue"))
    close_date = fmt_date(opp.get("closeDate"))
    assigned = _opp_assigned_name(opp) or "_unassigned_"
    contact_name = _opp_contact_name(opp)
    contact_id = opp.get("contactId", "")
    contact_display = f"{contact_name} ({contact_id})" if contact_name and contact_name != contact_id else (contact_name or contact_id or "_unknown_")

    lines = [
        f"## Opportunity: {opp.get('name', '(unnamed)')}",
        "",
        f"**Pipeline:** {pipeline_name} → **Stage:** {stage_name}  **Status:** {status}",
    ]
    value_line_parts = []
    if value:
        value_line_parts.append(f"**Value:** {value}")
    if close_date:
        value_line_parts.append(f"**Close Date:** {close_date}")
    value_line_parts.append(f"**Assigned:** {assigned}")
    lines.append("  ".join(value_line_parts))
    lines.append(f"**Contact:** {contact_display}")
    lines.append(
        f"**Created:** {opp.get('dateAdded') or '_unknown_'}  "
        f"**Updated:** {opp.get('dateUpdated') or '_unknown_'}"
    )

    custom_fields = opp.get("customFields") or []
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
            value_cf = cf.get("value")
            if value_cf is None:
                value_cf = ""
            lines.append(
                f"| {str(field_name).replace('|', r'\|')} "
                f"| {str(value_cf).replace('|', r'\|')} |"
            )

    return "\n".join(lines)


def register(mcp) -> None:  # noqa: ANN001
    @mcp.tool(
        name="ghl_opportunities_list",
        annotations={"title": "List opportunities", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def ghl_opportunities_list(params: OpportunitiesListInput) -> str:
        """List/search opportunities with filtering by pipeline, stage, status, contact, assignee, or free-text query.

        Use this to track all founders signups in your founders pipeline:
        ``ghl_opportunities_list(pipeline_id='founders-pipeline-id')``.
        """
        client = await get_client()
        account = settings.resolve_client(params.location_id)
        api_params: dict[str, Any] = {
            "location_id": account.location_id,
            "limit": params.limit,
            "skip": params.skip,
        }
        if params.pipeline_id:
            api_params["pipeline_id"] = params.pipeline_id
        if params.pipeline_stage_id:
            api_params["pipeline_stage_id"] = params.pipeline_stage_id
        if params.status:
            api_params["status"] = params.status.value if hasattr(params.status, "value") else params.status
        if params.contact_id:
            api_params["contact_id"] = params.contact_id
        if params.assigned_to:
            api_params["assigned_to"] = params.assigned_to
        if params.query:
            api_params["q"] = params.query
        result = await client.get("/opportunities/search", params=api_params, location_id=account.location_id)
        opps = result.get("opportunities", [])
        page = build_pagination_response(
            opps,
            total=extract_total(result, "total"),
            limit=params.limit, skip=params.skip,
            items_key="opportunities",
        )
        return format_response(page, params.response_format, markdown_renderer=_render_opp_list)

    @mcp.tool(
        name="ghl_opportunities_get",
        annotations={"title": "Get opportunity", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def ghl_opportunities_get(params: OpportunityGetInput) -> str:
        """Get full details for a single opportunity including custom fields."""
        client = await get_client()
        result = await client.get(f"/opportunities/{params.opportunity_id}", location_id=params.location_id)
        return format_response(result, params.response_format, markdown_renderer=_render_opp_detail)

    @mcp.tool(
        name="ghl_opportunities_create",
        annotations={"title": "Create opportunity", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def ghl_opportunities_create(params: OpportunityCreateInput) -> str:
        """Create a new opportunity. Requires pipeline, stage, name, and a contact ID."""
        client = await get_client()
        account = settings.resolve_client(params.location_id)
        body: dict[str, Any] = {
            "locationId": account.location_id,
            "pipelineId": params.pipeline_id,
            "pipelineStageId": params.pipeline_stage_id,
            "name": params.name,
            "contactId": params.contact_id,
            "status": params.status.value if hasattr(params.status, "value") else params.status,
        }
        if params.monetary_value is not None:
            body["monetaryValue"] = params.monetary_value
        if params.close_date:
            body["closeDate"] = params.close_date
        if params.source:
            body["source"] = params.source
        if params.assigned_to:
            body["assignedTo"] = params.assigned_to
        if params.custom_fields:
            body["customFields"] = params.custom_fields
        result = await client.post("/opportunities/", json=body, location_id=account.location_id)
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(
        name="ghl_opportunities_update",
        annotations={"title": "Update opportunity", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def ghl_opportunities_update(params: OpportunityUpdateInput) -> str:
        """Update fields on an opportunity. Only fields you pass are modified."""
        client = await get_client()
        body: dict[str, Any] = {}
        if params.name is not None: body["name"] = params.name
        if params.monetary_value is not None: body["monetaryValue"] = params.monetary_value
        if params.close_date is not None: body["closeDate"] = params.close_date
        if params.pipeline_stage_id is not None: body["pipelineStageId"] = params.pipeline_stage_id
        if params.status is not None:
            body["status"] = params.status.value if hasattr(params.status, "value") else params.status
        if params.assigned_to is not None: body["assignedTo"] = params.assigned_to
        if params.custom_fields is not None: body["customFields"] = params.custom_fields
        if not body:
            return "No fields to update."
        result = await client.put(f"/opportunities/{params.opportunity_id}", json=body, location_id=params.location_id)
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(
        name="ghl_opportunities_delete",
        annotations={"title": "Delete opportunity", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": True},
    )
    async def ghl_opportunities_delete(params: OpportunityIdInput) -> str:
        """Delete an opportunity permanently."""
        client = await get_client()
        await client.delete(f"/opportunities/{params.opportunity_id}", location_id=params.location_id)
        return f"Opportunity {params.opportunity_id} deleted."

    @mcp.tool(
        name="ghl_opportunities_move_stage",
        annotations={"title": "Move opportunity to stage", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def ghl_opportunities_move_stage(params: OpportunityMoveStageInput) -> str:
        """Move an opportunity to a different pipeline stage. Convenience wrapper around ``ghl_opportunities_update``."""
        client = await get_client()
        result = await client.put(
            f"/opportunities/{params.opportunity_id}",
            json={"pipelineStageId": params.pipeline_stage_id},
            location_id=params.location_id,
        )
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(
        name="ghl_opportunities_update_status",
        annotations={"title": "Update opportunity status", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def ghl_opportunities_update_status(params: OpportunityUpdateStatusInput) -> str:
        """Mark an opportunity won, lost, abandoned, or back to open."""
        client = await get_client()
        result = await client.put(
            f"/opportunities/{params.opportunity_id}/status",
            json={"status": params.status.value if hasattr(params.status, "value") else params.status},
            location_id=params.location_id,
        )
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(
        name="ghl_opportunities_search",
        annotations={"title": "Search opportunities", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def ghl_opportunities_search(params: OpportunitiesListInput) -> str:
        """Alias of ``ghl_opportunities_list`` with the ``query`` parameter emphasized for free-text search."""
        # Same backing call — kept as a separate tool so agents can find it via name.
        return await ghl_opportunities_list(params)  # type: ignore
