"""Calendar tools (6)."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ghl_mcp.client import get_client
from ghl_mcp.config import settings
from ghl_mcp.formatters import format_response
from ghl_mcp.models import ByIdInput, LocationScopedInput, ResponseFormat


class CalendarsListInput(LocationScopedInput):
    pass


class CalendarGetInput(ByIdInput):
    calendar_id: str = Field(..., min_length=1)


class CalendarCreateInput(LocationScopedInput):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    slug: str | None = Field(default=None, description="URL slug for the booking page.")
    slot_duration: int = Field(default=30, ge=5, le=480, description="Default slot length in minutes.")
    slot_interval: int = Field(default=30, ge=5, le=480, description="Interval between bookable slots.")
    slot_buffer: int = Field(default=0, ge=0, description="Buffer in minutes after each booking.")
    pre_buffer: int = Field(default=0, ge=0)
    min_booking_notice: int = Field(default=0, ge=0, description="Minimum hours of advance notice required.")


class CalendarUpdateInput(ByIdInput):
    calendar_id: str = Field(..., min_length=1)
    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    slot_duration: int | None = Field(default=None, ge=5, le=480)
    slot_interval: int | None = Field(default=None, ge=5, le=480)


class CalendarDeleteInput(ByIdInput):
    calendar_id: str = Field(..., min_length=1)


class CalendarFreeSlotsInput(ByIdInput):
    calendar_id: str = Field(..., min_length=1, description="Get from `ghl_calendars_list`.")
    start_date: str = Field(..., description="Start of the date range. ISO 8601 datetime (e.g. '2026-06-01T00:00:00Z') or Unix timestamp in milliseconds.")
    end_date: str = Field(..., description="End of the date range. ISO 8601 datetime (e.g. '2026-06-07T23:59:59Z') or Unix timestamp in milliseconds.")
    timezone: str | None = Field(default=None, description="IANA timezone name for returned slot times, e.g. 'Australia/Sydney', 'America/New_York'. Invalid timezones are rejected by GHL.")


def register(mcp) -> None:  # noqa: ANN001
    @mcp.tool(name="ghl_calendars_list", annotations={"title": "List calendars", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    async def ghl_calendars_list(params: CalendarsListInput) -> str:
        """List all calendars on a location."""
        client = await get_client()
        account = settings.resolve_client(params.location_id)
        result = await client.get("/calendars/", params={"locationId": account.location_id}, location_id=account.location_id)
        return format_response(result, params.response_format)

    @mcp.tool(name="ghl_calendars_get", annotations={"title": "Get calendar", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    async def ghl_calendars_get(params: CalendarGetInput) -> str:
        """Get full configuration of a calendar by ID."""
        client = await get_client()
        result = await client.get(f"/calendars/{params.calendar_id}", location_id=params.location_id)
        return format_response(result, params.response_format)

    @mcp.tool(name="ghl_calendars_create", annotations={"title": "Create calendar", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
    async def ghl_calendars_create(params: CalendarCreateInput) -> str:
        """Create a new calendar with bookable slot configuration."""
        client = await get_client()
        account = settings.resolve_client(params.location_id)
        body: dict[str, Any] = {
            "locationId": account.location_id,
            "name": params.name,
            "slotDuration": params.slot_duration,
            "slotInterval": params.slot_interval,
            "slotBuffer": params.slot_buffer,
            "preBuffer": params.pre_buffer,
            "minBookingNotice": params.min_booking_notice,
        }
        if params.description: body["description"] = params.description
        if params.slug: body["slug"] = params.slug
        result = await client.post("/calendars/", json=body, location_id=account.location_id)
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(name="ghl_calendars_update", annotations={"title": "Update calendar", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    async def ghl_calendars_update(params: CalendarUpdateInput) -> str:
        """Update calendar configuration."""
        client = await get_client()
        body: dict[str, Any] = {}
        if params.name is not None: body["name"] = params.name
        if params.description is not None: body["description"] = params.description
        if params.slot_duration is not None: body["slotDuration"] = params.slot_duration
        if params.slot_interval is not None: body["slotInterval"] = params.slot_interval
        if not body: return "No fields to update."
        result = await client.put(f"/calendars/{params.calendar_id}", json=body, location_id=params.location_id)
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(name="ghl_calendars_delete", annotations={"title": "Delete calendar", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": True})
    async def ghl_calendars_delete(params: CalendarDeleteInput) -> str:
        """Delete a calendar permanently. Existing appointments may also be cancelled."""
        client = await get_client()
        await client.delete(f"/calendars/{params.calendar_id}", location_id=params.location_id)
        return f"Calendar {params.calendar_id} deleted."

    @mcp.tool(name="ghl_calendars_get_free_slots", annotations={"title": "Get available calendar slots", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    async def ghl_calendars_get_free_slots(params: CalendarFreeSlotsInput) -> str:
        """Get available booking slots for a calendar in the given date range."""
        client = await get_client()
        api_params: dict[str, Any] = {"startDate": params.start_date, "endDate": params.end_date}
        if params.timezone: api_params["timezone"] = params.timezone
        result = await client.get(f"/calendars/{params.calendar_id}/free-slots", params=api_params, location_id=params.location_id)
        return format_response(result, params.response_format)
