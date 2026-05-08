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
    """Mixin: tools that operate on a single sub-account (location)."""

    location_id: str | None = Field(
        default=None,
        description=(
            "GHL Location/Sub-Account ID. Defaults to GHL_LOCATION_ID from "
            "environment if not provided."
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
