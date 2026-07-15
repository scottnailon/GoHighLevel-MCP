"""User tools (4)."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ghl_mcp.client import get_client
from ghl_mcp.config import settings
from ghl_mcp.formatters import format_response, md_table
from ghl_mcp.models import ByIdInput, LocationScopedInput, ResponseFormat


class UsersListInput(LocationScopedInput):
    pass


class UserGetInput(ByIdInput):
    user_id: str = Field(..., min_length=1)


class UserCreateInput(LocationScopedInput):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    password: str = Field(..., min_length=8, max_length=128, description="Initial password — user can change after first login.")
    role: str = Field(default="user", description="One of: 'admin', 'user'.")
    permissions: dict[str, bool] | None = Field(default=None, description="Granular permission flags.")


class UserUpdateInput(ByIdInput):
    user_id: str = Field(..., min_length=1)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=30)


def _render_users(payload: dict[str, Any]) -> str:
    users = payload.get("users", [])
    rows = [{
        "id": u.get("id"),
        "name": f"{u.get('firstName', '')} {u.get('lastName', '')}".strip(),
        "email": u.get("email", ""),
        "role": u.get("roles", {}).get("type", "") if isinstance(u.get("roles"), dict) else "",
    } for u in users]
    return md_table(rows, columns=[("id", "ID"), ("name", "Name"), ("email", "Email"), ("role", "Role")])


def register(mcp) -> None:  # noqa: ANN001
    @mcp.tool(name="ghl_users_list", annotations={"title": "List users", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    async def ghl_users_list(params: UsersListInput) -> str:
        """List all users with access to a location."""
        client = await get_client()
        account = settings.resolve_client(params.location_id)
        result = await client.get("/users/", params={"locationId": account.location_id}, location_id=account.location_id)
        return format_response(result, params.response_format, markdown_renderer=_render_users)

    @mcp.tool(name="ghl_users_get", annotations={"title": "Get user", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    async def ghl_users_get(params: UserGetInput) -> str:
        """Get full details of a single user."""
        client = await get_client()
        result = await client.get(f"/users/{params.user_id}", location_id=params.location_id)
        return format_response(result, params.response_format)

    @mcp.tool(name="ghl_users_create", annotations={"title": "Create user", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
    async def ghl_users_create(params: UserCreateInput) -> str:
        """Create a new user on a location."""
        client = await get_client()
        account = settings.resolve_client(params.location_id)
        body: dict[str, Any] = {
            "locationIds": [account.location_id],
            "firstName": params.first_name,
            "lastName": params.last_name,
            "email": params.email,
            "password": params.password,
            "type": "account",
            "role": params.role,
        }
        if params.phone: body["phone"] = params.phone
        if params.permissions: body["permissions"] = params.permissions
        result = await client.post("/users/", json=body, location_id=account.location_id)
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(name="ghl_users_update", annotations={"title": "Update user", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    async def ghl_users_update(params: UserUpdateInput) -> str:
        """Update a user's profile fields."""
        client = await get_client()
        body: dict[str, Any] = {}
        if params.first_name is not None: body["firstName"] = params.first_name
        if params.last_name is not None: body["lastName"] = params.last_name
        if params.email is not None: body["email"] = params.email
        if params.phone is not None: body["phone"] = params.phone
        if not body: return "No fields to update."
        result = await client.put(f"/users/{params.user_id}", json=body, location_id=params.location_id)
        return format_response(result, ResponseFormat.JSON)
