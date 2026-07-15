"""Form tools (2).

GHL forms are designed in the form builder UI. The API exposes listing forms
and retrieving submissions.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ghl_mcp.client import get_client
from ghl_mcp.config import settings
from ghl_mcp.formatters import format_response, md_pagination_footer, md_table
from ghl_mcp.models import BaseToolInput, LocationScopedInput, PaginationInput, ResponseFormat
from ghl_mcp.pagination import build_pagination_response, extract_total


class FormsListInput(LocationScopedInput):
    pass


class FormSubmissionsInput(LocationScopedInput, PaginationInput):
    form_id: str | None = Field(default=None, description="Filter to one form. Omit to get all submissions for the location.")
    start_date: str | None = Field(default=None, description="ISO 8601 — only submissions on or after this date.")
    end_date: str | None = Field(default=None)


def _render_forms_list(payload: dict[str, Any]) -> str:
    forms = payload.get("forms", [])
    rows = [{"id": f.get("id"), "name": f.get("name"), "location": f.get("locationId", "")} for f in forms]
    return md_table(rows, columns=[("id", "ID"), ("name", "Name"), ("location", "Location")])


def _render_submissions(payload: dict[str, Any]) -> str:
    subs = payload.get("submissions", payload.get("items", []))
    rows = [{
        "id": s.get("id"),
        "form": s.get("formId", "")[:12],
        "name": s.get("name", ""),
        "email": s.get("email", ""),
        "submitted": (s.get("createdAt") or s.get("dateAdded", ""))[:19],
    } for s in subs]
    table = md_table(rows, columns=[
        ("id", "ID"), ("form", "Form ID"), ("name", "Name"),
        ("email", "Email"), ("submitted", "Submitted"),
    ])
    if "has_more" in payload:
        footer = md_pagination_footer(
            count=payload["count"], total=payload["total"], skip=payload["skip"],
            limit=payload["limit"], has_more=payload["has_more"], next_skip=payload["next_skip"],
            pagination_note=payload.get("pagination_note"),
        )
        return f"{table}\n\n{footer}"
    return table


def register(mcp) -> None:  # noqa: ANN001
    @mcp.tool(name="ghl_forms_list", annotations={"title": "List forms", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    async def ghl_forms_list(params: FormsListInput) -> str:
        """List all forms configured on a location."""
        client = await get_client()
        account = settings.resolve_client(params.location_id)
        result = await client.get("/forms/", params={"locationId": account.location_id}, location_id=account.location_id)
        return format_response(result, params.response_format, markdown_renderer=_render_forms_list)

    @mcp.tool(name="ghl_forms_get_submissions", annotations={"title": "List form submissions", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    async def ghl_forms_get_submissions(params: FormSubmissionsInput) -> str:
        """List form submissions, optionally filtered by form ID or date range.

        Useful for retrieving the founders signup form data and importing it
        into the kickoff workflow.
        """
        client = await get_client()
        account = settings.resolve_client(params.location_id)
        api_params: dict[str, Any] = {
            "locationId": account.location_id,
            "limit": params.limit,
            "skip": params.skip,
        }
        if params.form_id: api_params["formId"] = params.form_id
        if params.start_date: api_params["startAt"] = params.start_date
        if params.end_date: api_params["endAt"] = params.end_date
        result = await client.get("/forms/submissions", params=api_params, location_id=account.location_id)
        subs = result.get("submissions", result.get("items", []))
        page = build_pagination_response(
            subs,
            total=extract_total(result, "total"),
            limit=params.limit, skip=params.skip,
            items_key="submissions",
        )
        return format_response(page, params.response_format, markdown_renderer=_render_submissions)
