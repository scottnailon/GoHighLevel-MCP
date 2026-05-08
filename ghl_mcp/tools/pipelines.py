"""Pipeline tools (5).

Sales pipelines containing ordered stages. Use ``ghl_opportunities_*`` to
manage deals within these pipelines.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ghl_mcp.client import get_client
from ghl_mcp.config import settings
from ghl_mcp.formatters import format_response, md_table
from ghl_mcp.models import BaseToolInput, LocationScopedInput, ResponseFormat


class PipelinesListInput(LocationScopedInput):
    pass


class PipelineGetInput(BaseToolInput):
    pipeline_id: str = Field(..., min_length=1)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class PipelineStage(BaseToolInput):
    name: str = Field(..., min_length=1, max_length=100)
    position: int = Field(..., ge=0)
    show_in_funnel: bool = Field(default=True)
    show_in_pie_chart: bool = Field(default=True)


class PipelineCreateInput(LocationScopedInput):
    name: str = Field(..., min_length=1, max_length=200)
    stages: list[PipelineStage] = Field(..., min_length=1, max_length=50)


class PipelineUpdateInput(BaseToolInput):
    pipeline_id: str = Field(..., min_length=1)
    name: str | None = Field(default=None, max_length=200)
    stages: list[PipelineStage] | None = Field(default=None, max_length=50)


class PipelineDeleteInput(BaseToolInput):
    pipeline_id: str = Field(..., min_length=1)


def _render_pipelines(payload: dict[str, Any]) -> str:
    pipelines = payload.get("pipelines", [])
    rows = []
    for p in pipelines:
        stages = p.get("stages", [])
        rows.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "stages": len(stages),
            "stage_names": " → ".join(s.get("name", "?") for s in sorted(stages, key=lambda x: x.get("position", 0))),
        })
    return md_table(rows, columns=[
        ("id", "ID"), ("name", "Name"), ("stages", "# Stages"), ("stage_names", "Stage flow"),
    ])


def _render_pipeline_detail(p: dict[str, Any]) -> str:
    inner = p.get("pipeline", p)
    lines = [f"### {inner.get('name', '?')} (`{inner.get('id', '?')}`)\n"]
    stages = sorted(inner.get("stages", []), key=lambda x: x.get("position", 0))
    for s in stages:
        lines.append(f"- **{s.get('position')}.** {s.get('name')} (`{s.get('id', '?')}`)")
    return "\n".join(lines)


def register(mcp) -> None:  # noqa: ANN001
    @mcp.tool(
        name="ghl_pipelines_list",
        annotations={"title": "List pipelines", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def ghl_pipelines_list(params: PipelinesListInput) -> str:
        """List all sales pipelines configured on a location, including their stages."""
        client = await get_client()
        location_id = settings.require_location_id(params.location_id)
        result = await client.get("/opportunities/pipelines", params={"locationId": location_id})
        return format_response(result, params.response_format, markdown_renderer=_render_pipelines)

    @mcp.tool(
        name="ghl_pipelines_get",
        annotations={"title": "Get pipeline details", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def ghl_pipelines_get(params: PipelineGetInput) -> str:
        """Get full details of a single pipeline including all stages."""
        client = await get_client()
        result = await client.get(f"/opportunities/pipelines/{params.pipeline_id}")
        return format_response(result, params.response_format, markdown_renderer=_render_pipeline_detail)

    @mcp.tool(
        name="ghl_pipelines_create",
        annotations={"title": "Create pipeline", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def ghl_pipelines_create(params: PipelineCreateInput) -> str:
        """Create a new sales pipeline with ordered stages.

        Each stage needs a ``name`` and ``position`` (0-indexed). Returns the
        new pipeline including assigned stage IDs.
        """
        client = await get_client()
        location_id = settings.require_location_id(params.location_id)
        body = {
            "locationId": location_id,
            "name": params.name,
            "stages": [
                {
                    "name": s.name,
                    "position": s.position,
                    "showInFunnel": s.show_in_funnel,
                    "showInPieChart": s.show_in_pie_chart,
                }
                for s in params.stages
            ],
        }
        result = await client.post("/opportunities/pipelines", json=body)
        return format_response(result, params.response_format, markdown_renderer=_render_pipeline_detail)

    @mcp.tool(
        name="ghl_pipelines_update",
        annotations={"title": "Update pipeline", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def ghl_pipelines_update(params: PipelineUpdateInput) -> str:
        """Update a pipeline's name or stages. Replacing ``stages`` replaces ALL stages — be careful with existing opportunities."""
        client = await get_client()
        body: dict[str, Any] = {}
        if params.name is not None:
            body["name"] = params.name
        if params.stages is not None:
            body["stages"] = [
                {"name": s.name, "position": s.position, "showInFunnel": s.show_in_funnel, "showInPieChart": s.show_in_pie_chart}
                for s in params.stages
            ]
        if not body:
            return "No updates provided. Pass `name` and/or `stages`."
        result = await client.put(f"/opportunities/pipelines/{params.pipeline_id}", json=body)
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(
        name="ghl_pipelines_delete",
        annotations={"title": "Delete pipeline", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": True},
    )
    async def ghl_pipelines_delete(params: PipelineDeleteInput) -> str:
        """Delete a pipeline. All opportunities within it are also deleted. CANNOT BE UNDONE."""
        client = await get_client()
        await client.delete(f"/opportunities/pipelines/{params.pipeline_id}")
        return f"Pipeline {params.pipeline_id} deleted."
