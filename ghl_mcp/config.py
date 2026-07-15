"""Environment-driven configuration for the GHL MCP server."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ClientAccount:
    """One client's credentials: a location ID and the PIT minted inside it."""

    location_id: str
    api_key: str
    label: str


@dataclass(frozen=True)
class Settings:
    """Immutable configuration loaded from environment variables.

    A frozen dataclass (rather than Pydantic BaseSettings) keeps the runtime
    dependency footprint small and avoids loading the validation machinery
    for what is essentially a handful of strings read once at startup.
    """

    clients: dict[str, ClientAccount] = field(default_factory=dict)
    default_location_id: str | None = None
    company_id: str | None = None
    base_url: str = "https://services.leadconnectorhq.com"
    api_version: str = "2021-07-28"
    timeout: float = 30.0
    max_retries: int = 3
    log_level: str = "INFO"

    def resolve_client(self, location_id: str | None = None) -> ClientAccount:
        """Return the ClientAccount to use for a tool call.

        Resolution order:
          1. An explicit ``location_id`` — must match a configured client, or
             this raises immediately rather than silently falling through to
             a different client's credentials.
          2. ``GHL_DEFAULT_LOCATION_ID``, if set and it names a configured
             client.
          3. If exactly one client is configured, use it — the common single-
             client setup shouldn't need a default pinned explicitly.

        Never guesses across multiple configured clients. An unresolvable
        call is a configuration error, not a request to act on "whichever
        client happens to be first" — that's how one client's data ends up
        written into another's account.
        """
        if not self.clients:
            raise RuntimeError(
                "No GHL clients are configured. Set GHL_CLIENTS (a JSON map of "
                "location_id -> {api_key, label}) or the legacy GHL_API_KEY / "
                "GHL_LOCATION_ID pair. See .env.example."
            )

        if location_id:
            client = self.clients.get(location_id)
            if client is None:
                known = ", ".join(f"{c.label} ({lid})" for lid, c in self.clients.items())
                raise ValueError(
                    f"Unknown location_id '{location_id}'. Configured clients: {known}"
                )
            return client

        if self.default_location_id:
            client = self.clients.get(self.default_location_id)
            if client is None:
                raise RuntimeError(
                    f"GHL_DEFAULT_LOCATION_ID is set to '{self.default_location_id}' "
                    "but no client with that location_id is configured in GHL_CLIENTS."
                )
            return client

        if len(self.clients) == 1:
            return next(iter(self.clients.values()))

        known = ", ".join(f"{c.label} ({lid})" for lid, c in self.clients.items())
        raise ValueError(
            f"Multiple clients configured ({known}) and no location_id was "
            "given for this call. Pass location_id explicitly, or set "
            "GHL_DEFAULT_LOCATION_ID to pick one as the default."
        )

    def require_company_id(self, override: str | None = None) -> str:
        """Return the explicit override, or the configured default, or raise.

        Not used by any tool in this build (no client-facing tool operates
        above location scope) — retained only because the startup pre-flight
        check auto-detects and logs this value as a courtesy.
        """
        if override:
            return override
        if self.company_id:
            return self.company_id
        if _resolved_company_id:
            return _resolved_company_id
        raise ValueError(
            "Could not determine the company ID. Set GHL_COMPANY_ID, pass "
            "company_id explicitly, or confirm a client's credentials are "
            "valid so startup auto-detection can run."
        )


def _parse_clients(raw: str | None) -> dict[str, ClientAccount]:
    """Parse GHL_CLIENTS, a JSON object mapping location_id -> {api_key, label}."""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"GHL_CLIENTS is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("GHL_CLIENTS must be a JSON object mapping location_id -> {api_key, label}.")

    clients: dict[str, ClientAccount] = {}
    for location_id, entry in data.items():
        if not isinstance(entry, dict) or not entry.get("api_key"):
            raise RuntimeError(f"GHL_CLIENTS entry for '{location_id}' is missing an api_key.")
        clients[location_id] = ClientAccount(
            location_id=location_id,
            api_key=entry["api_key"],
            label=entry.get("label") or location_id,
        )
    return clients


def _load_settings() -> Settings:
    clients = _parse_clients(os.getenv("GHL_CLIENTS"))

    # Legacy single-client env vars — kept working so an existing .env from
    # before multi-client support didn't need to migrate. Ignored if
    # GHL_CLIENTS is also set, to avoid two sources of truth.
    if not clients:
        legacy_key = os.getenv("GHL_API_KEY")
        legacy_location = os.getenv("GHL_LOCATION_ID")
        if legacy_key and legacy_location:
            clients[legacy_location] = ClientAccount(
                location_id=legacy_location, api_key=legacy_key, label=legacy_location
            )

    return Settings(
        clients=clients,
        default_location_id=os.getenv("GHL_DEFAULT_LOCATION_ID") or None,
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
