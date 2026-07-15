"""Workflow tools (2).

GHL workflows are designed in the visual workflow builder UI; the API is
read-only — there's no create/update endpoint. This module exposes listing
and triggering existing workflows for contacts.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ghl_mcp.client import get_client
from ghl_mcp.config import settings
from ghl_mcp.formatters import format_response, md_table
from ghl_mcp.models import ByIdInput, LocationScopedInput, ResponseFormat


class WorkflowsListInput(LocationScopedInput):
    pass


class WorkflowAddContactInput(ByIdInput):
    workflow_id: str = Field(..., min_length=1)
    contact_id: str = Field(..., min_length=1, description="The contact to enroll in the workflow.")
    event_start_time: str | None = Field(default=None, description="ISO 8601 datetime — when to start, if the workflow has time-based steps.")


def _render_workflow_list(payload: dict[str, Any]) -> str:
    workflows = payload.get("workflows", [])
    rows = [{
        "id": w.get("id"),
        "name": w.get("name"),
        "status": w.get("status", ""),
        "version": w.get("version", ""),
    } for w in workflows]
    return md_table(rows, columns=[
        ("id", "ID"), ("name", "Name"), ("status", "Status"), ("version", "Version"),
    ])


def register(mcp) -> None:  # noqa: ANN001
    @mcp.tool(name="ghl_workflows_list", annotations={"title": "List workflows", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    async def ghl_workflows_list(params: WorkflowsListInput) -> str:
        """List all workflows configured on a location.

        Returns ID, name, status (published/draft), and version. Use the IDs
        with ``ghl_workflows_add_contact`` to enroll contacts.
        """
        client = await get_client()
        account = settings.resolve_client(params.location_id)
        result = await client.get("/workflows/", params={"locationId": account.location_id}, location_id=account.location_id)
        return format_response(result, params.response_format, markdown_renderer=_render_workflow_list)

    @mcp.tool(name="ghl_workflows_add_contact", annotations={"title": "Enroll contact in workflow", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
    async def ghl_workflows_add_contact(params: WorkflowAddContactInput) -> str:
        """Enroll a contact in a workflow, triggering its first step.

        Use this to programmatically start automation sequences (e.g., enroll
        a new founder signup into the welcome workflow).
        """
        client = await get_client()
        body: dict[str, Any] = {}
        if params.event_start_time:
            body["eventStartTime"] = params.event_start_time
        result = await client.post(
            f"/contacts/{params.contact_id}/workflow/{params.workflow_id}",
            json=body or None,
            location_id=params.location_id,
        )
        return format_response(result, ResponseFormat.JSON)
