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

        Used by agency-scoped operations like sub-account management and
        snapshot operations which require an agency/company context.
        """
        if override:
            return override
        if self.company_id:
            return self.company_id
        raise ValueError(
            "No company_id provided and GHL_COMPANY_ID is not set. "
            "Agency-scoped operations require this. Get it from your "
            "GHL Agency Settings."
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
