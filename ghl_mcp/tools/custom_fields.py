"""Custom field tools (5).

Full CRUD for both contact and opportunity custom fields. This is the module
that unblocks bulk-creation of the kickoff form's ~20 custom fields.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from ghl_mcp.client import get_client
from ghl_mcp.config import settings
from ghl_mcp.formatters import format_response, md_table
from ghl_mcp.models import BaseToolInput, LocationScopedInput, ResponseFormat


class FieldDataType(str, Enum):
    """The data type of a custom field as accepted by the GHL V2 API."""

    TEXT = "TEXT"
    LARGE_TEXT = "LARGE_TEXT"
    NUMERICAL = "NUMERICAL"
    PHONE = "PHONE"
    MONETARY = "MONETARY"
    CHECKBOX = "CHECKBOX"
    SINGLE_OPTIONS = "SINGLE_OPTIONS"
    MULTIPLE_OPTIONS = "MULTIPLE_OPTIONS"
    DATE = "DATE"
    TEXTBOX_LIST = "TEXTBOX_LIST"
    FILE_UPLOAD = "FILE_UPLOAD"
    RADIO = "RADIO"
    SIGNATURE = "SIGNATURE"


class FieldModel(str, Enum):
    """Which object a custom field is attached to."""

    CONTACT = "contact"
    OPPORTUNITY = "opportunity"


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


class CustomFieldsListInput(LocationScopedInput):
    model: FieldModel | None = Field(
        default=None,
        description=(
            "Filter by object type: 'contact' or 'opportunity'. "
            "Omit to list all custom fields across both models."
        ),
    )


class CustomFieldGetInput(BaseToolInput):
    field_id: str = Field(..., min_length=1)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class CustomFieldOption(BaseToolInput):
    """One option in a SINGLE_OPTIONS / MULTIPLE_OPTIONS / RADIO field."""

    key: str = Field(..., min_length=1, max_length=100, description="Stable internal key.")
    label: str = Field(..., min_length=1, max_length=200, description="Display label shown to users.")


class CustomFieldCreateInput(LocationScopedInput):
    name: str = Field(..., min_length=1, max_length=200, description="Display name of the field.")
    data_type: FieldDataType = Field(..., description="The field's data type.")
    model: FieldModel = Field(default=FieldModel.CONTACT)
    placeholder: str | None = Field(default=None, max_length=200)
    position: int | None = Field(default=None, ge=0, description="Display order.")
    options: list[CustomFieldOption] | None = Field(
        default=None,
        description=(
            "Required for SINGLE_OPTIONS, MULTIPLE_OPTIONS, RADIO, CHECKBOX. "
            "List of {key, label} option objects."
        ),
        max_length=100,
    )
    accepted_formats: list[str] | None = Field(
        default=None,
        description="For FILE_UPLOAD: list of allowed extensions (e.g. ['pdf', 'docx']).",
    )
    is_multiple_file_allowed: bool | None = Field(default=None, description="For FILE_UPLOAD only.")
    max_number_of_files: int | None = Field(default=None, ge=1, le=20, description="For FILE_UPLOAD only.")


class CustomFieldUpdateInput(BaseToolInput):
    field_id: str = Field(..., min_length=1)
    name: str | None = Field(default=None, max_length=200)
    placeholder: str | None = Field(default=None, max_length=200)
    position: int | None = Field(default=None, ge=0)
    options: list[CustomFieldOption] | None = Field(default=None, max_length=100)


class CustomFieldDeleteInput(BaseToolInput):
    field_id: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def _render_field_list(payload: dict[str, Any]) -> str:
    fields = payload.get("customFields", payload.get("fields", []))
    rows = [{
        "id": f.get("id"),
        "name": f.get("name"),
        "type": f.get("dataType") or f.get("fieldDataType"),
        "key": f.get("fieldKey", ""),
        "model": f.get("model", ""),
    } for f in fields]
    return md_table(rows, columns=[
        ("id", "ID"),
        ("name", "Name"),
        ("type", "Type"),
        ("key", "Field key"),
        ("model", "Model"),
    ])


def _render_field_detail(f: dict[str, Any]) -> str:
    inner = f.get("customField", f)
    lines = [
        f"### {inner.get('name', '?')} (`{inner.get('id', '?')}`)",
        "",
        f"- **Type:** {inner.get('dataType') or inner.get('fieldDataType')}",
        f"- **Field key:** `{inner.get('fieldKey', '_unset_')}`",
        f"- **Model:** {inner.get('model', '_unset_')}",
        f"- **Placeholder:** {inner.get('placeholder', '_unset_')}",
    ]
    if inner.get("picklistOptions"):
        lines.append("- **Options:**")
        for opt in inner["picklistOptions"]:
            if isinstance(opt, dict):
                lines.append(f"  - `{opt.get('key', '?')}` → {opt.get('label', '?')}")
            else:
                lines.append(f"  - {opt}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register(mcp) -> None:  # noqa: ANN001
    @mcp.tool(
        name="ghl_custom_fields_list",
        annotations={
            "title": "List custom fields",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ghl_custom_fields_list(params: CustomFieldsListInput) -> str:
        """List all custom fields configured on a location.

        Returns each field's ID, name, data type, internal field key, and model.
        For picklist fields (SINGLE_OPTIONS, MULTIPLE_OPTIONS, RADIO, CHECKBOX) the
        available options are also included. Call this first to discover field IDs
        before populating ``custom_fields`` on contacts or opportunities.
        """
        client = await get_client()
        location_id = settings.require_location_id(params.location_id)
        api_params: dict[str, Any] = {}
        if params.model is not None:
            api_params["model"] = params.model.value if hasattr(params.model, "value") else params.model
        result = await client.get(
            f"/locations/{location_id}/customFields",
            params=api_params or None,
        )
        return format_response(result, params.response_format, markdown_renderer=_render_field_list)

    @mcp.tool(
        name="ghl_custom_fields_get",
        annotations={
            "title": "Get custom field",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ghl_custom_fields_get(params: CustomFieldGetInput) -> str:
        """Get full details for a single custom field, including its options for picklist types."""
        client = await get_client()
        result = await client.get(f"/locations/customFields/{params.field_id}")
        return format_response(result, params.response_format, markdown_renderer=_render_field_detail)

    @mcp.tool(
        name="ghl_custom_fields_create",
        annotations={
            "title": "Create custom field",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def ghl_custom_fields_create(params: CustomFieldCreateInput) -> str:
        """Create a new custom field on a location.

        For picklist types (SINGLE_OPTIONS, MULTIPLE_OPTIONS, RADIO, CHECKBOX),
        you MUST pass ``options``. For FILE_UPLOAD, optionally pass
        ``accepted_formats``, ``is_multiple_file_allowed``, ``max_number_of_files``.

        Returns the created field including its assigned ID and stable
        ``fieldKey``. The ``fieldKey`` is what you reference when populating
        the field via ``ghl_contacts_create`` or upserts.
        """
        client = await get_client()
        location_id = settings.require_location_id(params.location_id)

        body: dict[str, Any] = {
            "name": params.name,
            "dataType": params.data_type.value if hasattr(params.data_type, "value") else params.data_type,
            "model": params.model.value if hasattr(params.model, "value") else params.model,
        }
        if params.placeholder is not None:
            body["placeholder"] = params.placeholder
        if params.position is not None:
            body["position"] = params.position
        if params.options:
            body["options"] = [
                {"key": o.key, "label": o.label} for o in params.options
            ]
        if params.accepted_formats:
            body["acceptedFormats"] = ",".join(params.accepted_formats)
        if params.is_multiple_file_allowed is not None:
            body["isMultipleFileAllowed"] = params.is_multiple_file_allowed
        if params.max_number_of_files is not None:
            body["maxNumberOfFiles"] = params.max_number_of_files

        result = await client.post(f"/locations/{location_id}/customFields", json=body)
        return format_response(result, params.response_format, markdown_renderer=_render_field_detail)

    @mcp.tool(
        name="ghl_custom_fields_update",
        annotations={
            "title": "Update custom field",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ghl_custom_fields_update(params: CustomFieldUpdateInput) -> str:
        """Update name, placeholder, position, or picklist options of a custom field.

        Note: GHL does NOT allow changing a field's ``dataType`` or ``model``
        after creation. To change those, delete the field and recreate it.
        """
        client = await get_client()
        body: dict[str, Any] = {}
        if params.name is not None:
            body["name"] = params.name
        if params.placeholder is not None:
            body["placeholder"] = params.placeholder
        if params.position is not None:
            body["position"] = params.position
        if params.options is not None:
            body["options"] = [
                {"key": o.key, "label": o.label} for o in params.options
            ]
        if not body:
            return "No fields to update — pass at least one of: name, placeholder, position, options."
        result = await client.put(f"/locations/customFields/{params.field_id}", json=body)
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(
        name="ghl_custom_fields_delete",
        annotations={
            "title": "Delete custom field",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def ghl_custom_fields_delete(params: CustomFieldDeleteInput) -> str:
        """Delete a custom field permanently. Existing data on contacts/opportunities is also lost."""
        client = await get_client()
        await client.delete(f"/locations/customFields/{params.field_id}")
        return f"Custom field {params.field_id} deleted."
