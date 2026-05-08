"""Typed exceptions for GHL API errors.

Tools should catch ``GHLError`` (or subclasses) and surface the message to
the agent. The agent then has actionable text it can reason about — much
better than a generic 500 dump.
"""

from __future__ import annotations


class GHLError(Exception):
    """Base class for all GHL-related errors."""

    def __init__(self, message: str, *, status_code: int | None = None, details: str | None = None):
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class GHLAuthError(GHLError):
    """401/403 from GHL — token invalid, expired, or missing scopes."""


class GHLNotFoundError(GHLError):
    """404 — the resource doesn't exist or isn't accessible to this token."""


class GHLValidationError(GHLError):
    """400/422 — the request body or query failed GHL's validation."""


class GHLRateLimitError(GHLError):
    """429 — exceeded burst (100/10s) or daily (200k) limit."""


class GHLServerError(GHLError):
    """5xx from GHL upstream."""


class GHLTimeoutError(GHLError):
    """The HTTP request timed out before GHL responded."""


def map_status_to_exception(status_code: int, message: str, details: str | None = None) -> GHLError:
    """Map an HTTP status code to the appropriate exception subclass."""
    base_kwargs = {"status_code": status_code, "details": details}
    if status_code in (401, 403):
        hint = (
            " — verify your Private Integration Token is current (PITs auto-expire "
            "after 90 days of non-use) and that it has the required scopes."
        )
        return GHLAuthError(message + hint, **base_kwargs)
    if status_code == 404:
        return GHLNotFoundError(message, **base_kwargs)
    if status_code in (400, 422):
        return GHLValidationError(message, **base_kwargs)
    if status_code == 429:
        return GHLRateLimitError(
            message + " — rate limits are 100 req/10s burst, 200k/day. "
            "Reduce request frequency or batch operations.",
            **base_kwargs,
        )
    if status_code >= 500:
        return GHLServerError(message + " — GHL upstream issue, retry may succeed.", **base_kwargs)
    return GHLError(message, **base_kwargs)
