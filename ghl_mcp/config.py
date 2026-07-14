"""Environment-driven configuration for the GHL MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Immutable configuration loaded from environment variables.

    A frozen dataclass (rather than Pydantic BaseSettings) keeps the runtime
    dependency footprint small and avoids loading the validation machinery
    for what is essentially a handful of strings read once at startup.
    """

    api_key: str | None
    location_id: str | None
    company_id: str | None
    base_url: str
    api_version: str
    timeout: float
    max_retries: int
    log_level: str

    def require_api_key(self) -> str:
        """Return the API key or raise a clear error if not configured."""
        if not self.api_key:
            raise RuntimeError(
                "GHL_API_KEY is not configured. Set it in your environment "
                "or .env file. Generate a Private Integration Token at: "
                "GoHighLevel → Settings → Private Integrations."
            )
        return self.api_key

    def require_location_id(self, override: str | None = None) -> str:
        """Return the explicit override, or the configured default, or raise."""
        if override:
            return override
        if self.location_id:
            return self.location_id
        raise ValueError(
            "No location_id provided and GHL_LOCATION_ID is not set. "
            "Either pass location_id explicitly or configure a default."
        )

    def require_company_id(self, override: str | None = None) -> str:
        """Return the explicit override, or the configured default, or raise.

        Not used by any tool in this build (no client-facing tool operates
        above location scope) — retained only because the startup pre-flight
        check auto-detects and logs this value as a courtesy.

        Resolution order:
          1. An explicit ``override`` passed to the call.
          2. ``GHL_COMPANY_ID`` from the environment, if set.
          3. The value auto-detected from the location at startup
             (see :func:`set_resolved_company_id`).
        """
        if override:
            return override
        if self.company_id:
            return self.company_id
        if _resolved_company_id:
            return _resolved_company_id
        raise ValueError(
            "Could not determine the company ID. Set GHL_COMPANY_ID, pass "
            "company_id explicitly, or confirm GHL_API_KEY and "
            "GHL_LOCATION_ID are valid so startup auto-detection can run."
        )


def _load_settings() -> Settings:
    return Settings(
        api_key=os.getenv("GHL_API_KEY") or None,
        location_id=os.getenv("GHL_LOCATION_ID") or None,
        company_id=os.getenv("GHL_COMPANY_ID") or None,
        base_url=os.getenv("GHL_BASE_URL", "https://services.leadconnectorhq.com").rstrip("/"),
        api_version=os.getenv("GHL_API_VERSION", "2021-07-28"),
        timeout=float(os.getenv("GHL_TIMEOUT", "30")),
        max_retries=int(os.getenv("GHL_MAX_RETRIES", "3")),
        log_level=os.getenv("GHL_LOG_LEVEL", "INFO").upper(),
    )


# Module-level singleton — loaded once per process.
settings = _load_settings()


# ---------------------------------------------------------------------------
# Auto-detected company ID
# ---------------------------------------------------------------------------
# The agency/company ID is present on every location record, so it can be read
# once at startup from GET /locations/{id} rather than asking the user to find
# it in Agency Settings. It is stored here (module-level, mutable) because
# Settings itself is a frozen dataclass. require_company_id() falls back to this
# value when GHL_COMPANY_ID is not explicitly set.
_resolved_company_id: str | None = None


def set_resolved_company_id(company_id: str | None) -> None:
    """Record the company ID auto-detected from the location at startup.

    Called by the startup pre-flight check once it has a valid location
    response. A no-op for falsy values so a failed lookup never clobbers a
    previously good value.
    """
    global _resolved_company_id
    if company_id:
        _resolved_company_id = company_id


def get_resolved_company_id() -> str | None:
    """Return the company ID auto-detected at startup, if any."""
    return _resolved_company_id
