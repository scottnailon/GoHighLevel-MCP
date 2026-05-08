"""Snapshot tools (4).

Snapshots are GHL's mechanism for replicating a configured location across many
sub-accounts — the cornerstone of any SaaS reseller workflow. Tools here let
you list available snapshots, retrieve details, and import a snapshot into a
target sub-account.

Note: snapshot endpoints require an agency-scoped token and the
``snapshots.readonly`` / ``snapshots.write`` scopes.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ghl_mcp.client import get_client
from ghl_mcp.config import settings
from ghl_mcp.formatters import format_response, md_table
from ghl_mcp.models import BaseToolInput, CompanyScopedInput, ResponseFormat


class SnapshotsListInput(CompanyScopedInput):
    """List all snapshots available to the agency."""


class SnapshotGetInput(BaseToolInput):
    snapshot_id: str = Field(..., min_length=1)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class SnapshotImportInput(CompanyScopedInput):
    snapshot_id: str = Field(..., min_length=1, description="The snapshot to import.")
    location_id: str = Field(..., min_length=1, description="Target sub-account ID receiving the snapshot.")


class SnapshotShareInput(CompanyScopedInput):
    snapshot_id: str = Field(..., min_length=1)
    share_type: str = Field(default="link", description="Currently only 'link' is supported by GHL.")
    relationship_type: str | None = Field(default=None, description="Optional relationship qualifier.")


def _render_snapshot_list(payload: dict[str, Any]) -> str:
    snapshots = payload.get("snapshots", [])
    rows = [{
        "id": s.get("id"),
        "name": s.get("name"),
        "type": s.get("type", ""),
    } for s in snapshots]
    return md_table(rows, columns=[
        ("id", "ID"), ("name", "Name"), ("type", "Type"),
    ])


def register(mcp) -> None:  # noqa: ANN001
    @mcp.tool(
        name="ghl_snapshots_list",
        annotations={
            "title": "List snapshots",
            "readOnlyHint": True, "destructiveHint": False,
            "idempotentHint": True, "openWorldHint": True,
        },
    )
    async def ghl_snapshots_list(params: SnapshotsListInput) -> str:
        """List all snapshots available to your agency.

        Returns snapshot ID, name, and type for each. Use this to discover
        which snapshot to import into a new sub-account during onboarding.
        """
        client = await get_client()
        company_id = settings.require_company_id(params.company_id)
        result = await client.get("/snapshots/", params={"companyId": company_id})
        return format_response(result, params.response_format, markdown_renderer=_render_snapshot_list)

    @mcp.tool(
        name="ghl_snapshots_get",
        annotations={
            "title": "Get snapshot details",
            "readOnlyHint": True, "destructiveHint": False,
            "idempotentHint": True, "openWorldHint": True,
        },
    )
    async def ghl_snapshots_get(params: SnapshotGetInput) -> str:
        """Get full details for a snapshot, including the assets it contains."""
        client = await get_client()
        result = await client.get(f"/snapshots/{params.snapshot_id}")
        return format_response(result, params.response_format)

    @mcp.tool(
        name="ghl_snapshots_import",
        annotations={
            "title": "Import snapshot into sub-account",
            "readOnlyHint": False, "destructiveHint": False,
            "idempotentHint": False, "openWorldHint": True,
        },
    )
    async def ghl_snapshots_import(params: SnapshotImportInput) -> str:
        """Import (load) a snapshot into a target sub-account.

        This copies the snapshot's pipelines, workflows, custom fields, forms,
        funnels, calendars, etc. into the destination location. The operation
        is asynchronous on GHL's side; this tool returns immediately with the
        import job ID.
        """
        client = await get_client()
        company_id = settings.require_company_id(params.company_id)
        body = {
            "companyId": company_id,
            "snapshotId": params.snapshot_id,
            "locationId": params.location_id,
        }
        result = await client.post("/snapshots/load", json=body)
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(
        name="ghl_snapshots_share_link",
        annotations={
            "title": "Generate snapshot share link",
            "readOnlyHint": False, "destructiveHint": False,
            "idempotentHint": True, "openWorldHint": True,
        },
    )
    async def ghl_snapshots_share_link(params: SnapshotShareInput) -> str:
        """Generate a shareable link to a snapshot, allowing other agencies to clone it."""
        client = await get_client()
        company_id = settings.require_company_id(params.company_id)
        body = {
            "companyId": company_id,
            "shareType": params.share_type,
        }
        if params.relationship_type:
            body["relationshipType"] = params.relationship_type
        result = await client.post(f"/snapshots/{params.snapshot_id}/share/link", json=body)
        return format_response(result, ResponseFormat.JSON)
