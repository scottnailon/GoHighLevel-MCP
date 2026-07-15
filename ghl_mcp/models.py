"""Shared Pydantic models used across multiple tool modules."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ResponseFormat(str, Enum):
    """How tool output should be rendered.

    ``markdown`` — concise, human-readable. Recommended for agent context
    economy.

    ``json`` — full structured data. Use when downstream code needs to
    consume the result programmatically.
    """

    MARKDOWN = "markdown"
    JSON = "json"


class BaseToolInput(BaseModel):
    """Base class for all tool inputs.

    Sets project-wide Pydantic config so individual tools don't have to
    repeat it.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
        use_enum_values=True,
    )


class PaginationInput(BaseToolInput):
    """Standard pagination parameters for list operations."""

    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results to return (1-100).",
    )
    skip: int = Field(
        default=0,
        ge=0,
        description="Number of results to skip for pagination.",
    )


class LocationScopedInput(BaseToolInput):
    """Mixin: tools that operate on a single sub-account (location) and send
    ``locationId`` in the request itself (list/search/create)."""

    location_id: str | None = Field(
        default=None,
        description=(
            "GHL Location/Sub-Account ID. Selects which configured client's "
            "credentials to use. Omit to use the configured default client, "
            "or the sole configured client if only one exists."
        ),
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' (concise) or 'json' (structured).",
    )


class ByIdInput(BaseToolInput):
    """Mixin: tools that address a resource purely by its own ID (get/update/
    delete by contact_id, opportunity_id, etc.) — the GHL endpoint itself
    needs no locationId, but multiple clients may be configured, so
    location_id is still needed to select whose credentials authenticate
    the call."""

    location_id: str | None = Field(
        default=None,
        description=(
            "GHL Location/Sub-Account ID whose credentials should make this "
            "call. Omit to use the configured default client, or the sole "
            "configured client if only one exists. Required if multiple "
            "clients are configured and none is set as default."
        ),
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' (concise) or 'json' (structured).",
    )


class CompanyScopedInput(BaseToolInput):
    """Mixin: tools that operate at the agency/company level."""

    company_id: str | None = Field(
        default=None,
        description=(
            "GHL Agency/Company ID. Defaults to GHL_COMPANY_ID from "
            "environment if not provided."
        ),
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' (concise) or 'json' (structured).",
    )
