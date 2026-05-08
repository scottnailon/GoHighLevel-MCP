"""Appointment tools (4): book, list, get, update/cancel."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from ghl_mcp.client import get_client
from ghl_mcp.formatters import format_response
from ghl_mcp.models import BaseToolInput, ResponseFormat


class AppointmentStatus(str, Enum):
    NEW = "new"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    SHOWED = "showed"
    NOSHOW = "noshow"
    INVALID = "invalid"


class AppointmentsListInput(BaseToolInput):
    calendar_id: str = Field(..., min_length=1, description="Get from `ghl_calendars_list`.")
    contact_id: str | None = Field(default=None, description="Filter to appointments for a specific contact. Get from `ghl_contacts_list`.")
    user_id: str | None = Field(default=None, description="Filter to appointments assigned to a specific user. Get from `ghl_users_list`.")
    start_date: str | None = Field(default=None, description="ISO 8601 UTC datetime, e.g. '2026-06-01T00:00:00Z'. Not a Unix timestamp.")
    end_date: str | None = Field(default=None, description="ISO 8601 UTC datetime, e.g. '2026-06-30T23:59:59Z'. Not a Unix timestamp.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class AppointmentGetInput(BaseToolInput):
    appointment_id: str = Field(..., min_length=1)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class AppointmentCreateInput(BaseToolInput):
    calendar_id: str = Field(..., min_length=1, description="Get from `ghl_calendars_list`.")
    contact_id: str = Field(..., min_length=1, description="Get from `ghl_contacts_list` or `ghl_contacts_upsert`.")
    start_time: str = Field(
        ...,
        description="ISO 8601 UTC datetime, e.g. '2026-05-20T14:00:00Z'. This is NOT a Unix timestamp — must be a formatted datetime string.",
    )
    end_time: str | None = Field(
        default=None,
        description="ISO 8601 UTC datetime, e.g. '2026-05-20T15:00:00Z'. If omitted, defaults to start_time + calendar slot_duration.",
    )
    title: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=5000)
    assigned_user_id: str | None = Field(default=None, description="GHL user ID to assign the appointment to. Get from `ghl_users_list`.")
    appointment_status: AppointmentStatus = Field(default=AppointmentStatus.CONFIRMED)


class AppointmentUpdateInput(BaseToolInput):
    appointment_id: str = Field(..., min_length=1)
    start_time: str | None = Field(
        default=None,
        description="ISO 8601 UTC datetime, e.g. '2026-05-20T14:00:00Z'. This is NOT a Unix timestamp.",
    )
    end_time: str | None = Field(
        default=None,
        description="ISO 8601 UTC datetime, e.g. '2026-05-20T15:00:00Z'. This is NOT a Unix timestamp.",
    )
    title: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=5000)
    appointment_status: AppointmentStatus | None = Field(default=None, description="Valid values: new, confirmed, cancelled, showed, noshow, invalid.")


def register(mcp) -> None:  # noqa: ANN001
    @mcp.tool(name="ghl_appointments_list", annotations={"title": "List appointments", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    async def ghl_appointments_list(params: AppointmentsListInput) -> str:
        """List appointments on a calendar, optionally filtered by contact, user, or date range."""
        client = await get_client()
        api_params: dict[str, Any] = {"calendarId": params.calendar_id}
        if params.contact_id: api_params["contactId"] = params.contact_id
        if params.user_id: api_params["userId"] = params.user_id
        if params.start_date: api_params["startDate"] = params.start_date
        if params.end_date: api_params["endDate"] = params.end_date
        result = await client.get("/calendars/events/appointments", params=api_params)
        return format_response(result, params.response_format)

    @mcp.tool(name="ghl_appointments_get", annotations={"title": "Get appointment", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    async def ghl_appointments_get(params: AppointmentGetInput) -> str:
        """Get full details of a single appointment."""
        client = await get_client()
        result = await client.get(f"/calendars/events/appointments/{params.appointment_id}")
        return format_response(result, params.response_format)

    @mcp.tool(name="ghl_appointments_create", annotations={"title": "Book appointment", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
    async def ghl_appointments_create(params: AppointmentCreateInput) -> str:
        """Book an appointment on a calendar for a contact at a specific time."""
        client = await get_client()
        body: dict[str, Any] = {
            "calendarId": params.calendar_id,
            "contactId": params.contact_id,
            "startTime": params.start_time,
            "appointmentStatus": params.appointment_status.value if hasattr(params.appointment_status, "value") else params.appointment_status,
        }
        if params.end_time: body["endTime"] = params.end_time
        if params.title: body["title"] = params.title
        if params.notes: body["notes"] = params.notes
        if params.assigned_user_id: body["assignedUserId"] = params.assigned_user_id
        result = await client.post("/calendars/events/appointments", json=body)
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(name="ghl_appointments_update", annotations={"title": "Update appointment", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    async def ghl_appointments_update(params: AppointmentUpdateInput) -> str:
        """Update or cancel an appointment. Pass appointment_status='cancelled' to cancel."""
        client = await get_client()
        body: dict[str, Any] = {}
        if params.start_time: body["startTime"] = params.start_time
        if params.end_time: body["endTime"] = params.end_time
        if params.title: body["title"] = params.title
        if params.notes: body["notes"] = params.notes
        if params.appointment_status:
            body["appointmentStatus"] = params.appointment_status.value if hasattr(params.appointment_status, "value") else params.appointment_status
        if not body: return "No fields to update."
        result = await client.put(f"/calendars/events/appointments/{params.appointment_id}", json=body)
        return format_response(result, ResponseFormat.JSON)
