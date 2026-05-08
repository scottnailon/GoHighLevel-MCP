"""Location / sub-account management tools (6).

Critical for SaaS / white-label workflows. Lets you create new sub-accounts,
update their settings, retrieve metadata, and delete unused ones.

Most operations require an agency-scoped Private Integration Token with the
``saas/locations.read`` and ``saas/location.write`` scopes.
"""

from __future__ import annotations

from typing import Any
from zoneinfo import available_timezones

from pydantic import Field, field_validator

from ghl_mcp.client import get_client
from ghl_mcp.config import settings
from ghl_mcp.formatters import format_response, md_pagination_footer, md_table
from ghl_mcp.models import BaseToolInput, CompanyScopedInput, PaginationInput, ResponseFormat
from ghl_mcp.pagination import build_pagination_response, extract_total


class LocationsListInput(CompanyScopedInput, PaginationInput):
    search: str | None = Field(default=None, max_length=200, description="Free-text search across location names.")


class LocationGetInput(BaseToolInput):
    location_id: str = Field(..., min_length=1)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


_VALID_TIMEZONES = available_timezones()


def _validate_timezone(v: str | None) -> str | None:
    if v is not None and v not in _VALID_TIMEZONES:
        raise ValueError(
            f"'{v}' is not a valid IANA timezone. "
            "Examples: 'Australia/Sydney', 'America/New_York', 'Europe/London'."
        )
    return v


class LocationCreateInput(CompanyScopedInput):
    name: str = Field(..., min_length=1, max_length=200, description="Business name for the new sub-account.")
    business_email: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=30, description="Business phone number in E.164 format, e.g. +61412345678 or +14155551234.")
    address: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str = Field(default="AU", max_length=2, description="ISO 2-letter country code. Defaults to AU.")
    postal_code: str | None = Field(default=None, max_length=20)
    website: str | None = Field(default=None, max_length=300)
    timezone: str = Field(default="Australia/Sydney", description="IANA timezone name, e.g. 'Australia/Sydney', 'America/New_York'. Invalid timezones are rejected.")
    snapshot_id: str | None = Field(
        default=None,
        description="Optional snapshot to load on creation. Combines two operations into one.",
    )

    @field_validator("timezone", mode="after")
    @classmethod
    def validate_timezone(cls, v: str | None) -> str | None:
        return _validate_timezone(v)


class LocationUpdateInput(BaseToolInput):
    location_id: str = Field(..., min_length=1)
    name: str | None = Field(default=None, max_length=200)
    business_email: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=30, description="Business phone number in E.164 format, e.g. +61412345678 or +14155551234.")
    address: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=2, description="ISO 2-letter country code, e.g. 'AU', 'US', 'GB'.")
    postal_code: str | None = Field(default=None, max_length=20)
    website: str | None = Field(default=None, max_length=300)
    timezone: str | None = Field(default=None, description="IANA timezone name, e.g. 'Australia/Sydney', 'America/New_York'. Invalid timezones are rejected.")

    @field_validator("timezone", mode="after")
    @classmethod
    def validate_timezone(cls, v: str | None) -> str | None:
        return _validate_timezone(v)


class LocationDeleteInput(CompanyScopedInput):
    location_id: str = Field(..., min_length=1)
    delete_twilio_account: bool = Field(default=True, description="Whether to also delete the associated Twilio sub-account.")


def _render_locations_list(payload: dict[str, Any]) -> str:
    locations = payload.get("locations", [])
    rows = [{
        "id": loc.get("id"),
        "name": loc.get("name"),
        "email": loc.get("email") or loc.get("businessEmail", ""),
        "country": loc.get("country", ""),
        "timezone": loc.get("timezone", ""),
    } for loc in locations]
    table = md_table(rows, columns=[
        ("id", "ID"), ("name", "Name"), ("email", "Email"),
        ("country", "Country"), ("timezone", "Timezone"),
    ])
    footer = md_pagination_footer(
        count=payload["count"], total=payload["total"], skip=payload["skip"],
        limit=payload["limit"], has_more=payload["has_more"], next_skip=payload["next_skip"],
        pagination_note=payload.get("pagination_note"),
    )
    return f"{table}\n\n{footer}"


def _render_location_detail(loc: dict[str, Any]) -> str:
    inner = loc.get("location", loc)
    lines = [
        f"### {inner.get('name', '?')} (`{inner.get('id', '?')}`)",
        "",
        f"- **Business email:** {inner.get('email') or inner.get('businessEmail', '_unset_')}",
        f"- **Phone:** {inner.get('phone', '_unset_')}",
        f"- **Address:** {inner.get('address', '')}, {inner.get('city', '')} {inner.get('state', '')} {inner.get('postalCode', '')}",
        f"- **Country:** {inner.get('country', '_unset_')}",
        f"- **Timezone:** {inner.get('timezone', '_unset_')}",
        f"- **Website:** {inner.get('website', '_unset_')}",
        f"- **Created:** {inner.get('dateAdded', '_unknown_')}",
    ]
    return "\n".join(lines)


def _build_location_body(params: BaseToolInput, *, include_company: str | None = None) -> dict[str, Any]:
    payload = params.model_dump(exclude_none=True)
    for k in ("location_id", "response_format", "company_id", "delete_twilio_account"):
        payload.pop(k, None)
    snake_to_camel = {
        "business_email": "email",
        "postal_code": "postalCode",
        "snapshot_id": "snapshotId",
    }
    body = {snake_to_camel.get(k, k): v for k, v in payload.items()}
    if include_company:
        body["companyId"] = include_company
    return body


def register(mcp) -> None:  # noqa: ANN001
    @mcp.tool(
        name="ghl_locations_list",
        annotations={"title": "List sub-accounts", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def ghl_locations_list(params: LocationsListInput) -> str:
        """List all sub-accounts (locations) under your agency.

        Returns ID, name, email, country, and timezone for each. Use ``search``
        to free-text filter. Pagination via ``skip``/``limit``.
        """
        client = await get_client()
        company_id = settings.require_company_id(params.company_id)
        result = await client.get(
            "/locations/search",
            params={
                "companyId": company_id,
                "limit": params.limit,
                "skip": params.skip,
                "query": params.search,
            },
        )
        locations = result.get("locations", [])
        page = build_pagination_response(
            locations,
            total=extract_total(result, "total"),
            limit=params.limit, skip=params.skip,
            items_key="locations",
        )
        return format_response(page, params.response_format, markdown_renderer=_render_locations_list)

    @mcp.tool(
        name="ghl_locations_get",
        annotations={"title": "Get sub-account details", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def ghl_locations_get(params: LocationGetInput) -> str:
        """Get full configuration for a single sub-account by its location ID."""
        client = await get_client()
        result = await client.get(f"/locations/{params.location_id}")
        return format_response(result, params.response_format, markdown_renderer=_render_location_detail)

    @mcp.tool(
        name="ghl_locations_create",
        annotations={"title": "Create new sub-account", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def ghl_locations_create(params: LocationCreateInput) -> str:
        """Create a new sub-account (location) under your agency.

        Returns the new location's ID and configuration. If ``snapshot_id``
        is provided, that snapshot is loaded into the new location as part
        of creation — saving a separate ``ghl_snapshots_import`` call.

        This is the entrypoint for onboarding new SaaS clients programmatically.
        """
        client = await get_client()
        company_id = settings.require_company_id(params.company_id)
        body = _build_location_body(params, include_company=company_id)
        result = await client.post("/locations/", json=body)
        return format_response(result, params.response_format, markdown_renderer=_render_location_detail)

    @mcp.tool(
        name="ghl_locations_update",
        annotations={"title": "Update sub-account", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def ghl_locations_update(params: LocationUpdateInput) -> str:
        """Update business profile fields on an existing sub-account."""
        client = await get_client()
        body = _build_location_body(params)
        if not body:
            return "No fields to update — pass at least one updatable field."
        result = await client.put(f"/locations/{params.location_id}", json=body)
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(
        name="ghl_locations_delete",
        annotations={"title": "Delete sub-account", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": True},
    )
    async def ghl_locations_delete(params: LocationDeleteInput) -> str:
        """Permanently delete a sub-account. THIS IS DESTRUCTIVE — all data, contacts, and configuration are lost.

        By default also deletes the associated Twilio sub-account. Set
        ``delete_twilio_account=false`` if you've migrated the Twilio number elsewhere.
        """
        client = await get_client()
        company_id = settings.require_company_id(params.company_id)
        await client.delete(
            f"/locations/{params.location_id}",
            params={
                "companyId": company_id,
                "deleteTwilioAccount": "true" if params.delete_twilio_account else "false",
            },
        )
        return f"Sub-account {params.location_id} deleted (Twilio: {params.delete_twilio_account})."
