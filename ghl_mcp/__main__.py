"""CLI entrypoint: ``python -m ghl_mcp``."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import urllib.error
import urllib.request

from ghl_mcp.client import USER_AGENT
from ghl_mcp.config import ClientAccount, set_resolved_company_id, settings
from ghl_mcp.server import mcp


def main() -> None:
    """Run the MCP server over stdio."""
    # IMPORTANT: stdio MCP servers must NOT log to stdout.
    # Logs go to stderr so they don't corrupt the JSON-RPC stream.
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )
    logger = logging.getLogger("ghl_mcp")

    _check_credentials(logger)
    asyncio.run(_check_tokens_live(logger))

    client_summary = ", ".join(f"{c.label} ({lid})" for lid, c in settings.clients.items()) or "none configured"
    transport = os.environ.get("GHL_MCP_TRANSPORT", "stdio").lower()
    logger.info(
        "Starting GoHighLevel MCP server v2.0.0 (clients: %s, transport: %s)",
        client_summary, transport,
    )

    if transport in ("http", "streamable-http", "streamable_http"):
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


async def _check_tokens_live(logger: logging.Logger) -> None:
    """Make a lightweight live API call per configured client to verify each
    PIT is valid.

    Uses GET /locations/{location_id} — cheap, unambiguous, requires a working
    token. Runs once per configured client so a stale token for client B
    doesn't go unnoticed just because client A's happens to be fine.

    * 200 → token valid; auto-detect and stash the company ID (first success
      wins, since every client's PIT belongs to the same agency here).
    * 401 → token expired or invalid; log a clear remediation banner naming
      the affected client.
    * 403 → token present but missing required scopes; log a scopes banner.
    * Anything else (4xx other, 5xx, network error) → DEBUG only; never
      blocks startup so that transient network hiccups don't prevent the
      server from starting.
    """
    for account in settings.clients.values():
        await _check_token_live(logger, account)


async def _check_token_live(logger: logging.Logger, account: ClientAccount) -> None:
    url = f"{settings.base_url}/locations/{account.location_id}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {account.api_key}",
            "Version": settings.api_version,
            "Accept": "application/json",
            # GHL sits behind Cloudflare, which blocks the default Python
            # urllib User-Agent with a 403 (Error 1010). Send an explicit UA
            # so the pre-flight check isn't misreported as a scope failure.
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )

    sep = "=" * 60
    status_code: int | None = None

    try:
        # Run the blocking urllib call in a thread so we stay async-friendly.
        loop = asyncio.get_running_loop()
        with await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=10)) as resp:
            # 2xx — token is valid. Read the location record so we can
            # auto-detect the agency/company ID from it.
            logger.debug(
                "PIT pre-flight check passed for %s (HTTP 2xx from /locations/%s)",
                account.label, account.location_id,
            )
            _auto_detect_company_id(logger, resp.read())
            return
    except urllib.error.HTTPError as exc:
        status_code = exc.code
    except Exception as exc:  # noqa: BLE001 — network errors, DNS failures, etc.
        logger.debug("PIT pre-flight check skipped for %s (network error: %s)", account.label, exc)
        return

    if status_code == 401:
        logger.warning(sep)
        logger.warning("GoHighLevel MCP — TOKEN EXPIRED OR INVALID (%s)", account.label)
        logger.warning(sep)
        logger.warning("The live API check for '%s' (%s) returned HTTP 401 Unauthorized.", account.label, account.location_id)
        logger.warning("That client's Private Integration Token (PIT) is either")
        logger.warning("expired or has been revoked.")
        logger.warning("")
        logger.warning("Private Integration Tokens expire after 90 days of non-use.")
        logger.warning("")
        logger.warning("To regenerate it:")
        logger.warning("  1. Log in to GoHighLevel as that client's sub-account")
        logger.warning("  2. Go to Settings → Private Integrations")
        logger.warning("  3. Find your integration and click 'Regenerate Token'")
        logger.warning("     (or create a new integration if needed)")
        logger.warning("  4. Copy the new token — it starts with 'pit-'")
        logger.warning("  5. Update this client's entry in GHL_CLIENTS (or GHL_API_KEY")
        logger.warning("     if this is your legacy single-client setup)")
        logger.warning("  6. Restart Claude Desktop / Claude Code")
        logger.warning("")
        logger.warning("The server will start but calls for this client will fail")
        logger.warning("until the token is replaced.")
        logger.warning(sep)
    elif status_code == 403:
        logger.warning(sep)
        logger.warning("GoHighLevel MCP — TOKEN HAS INSUFFICIENT SCOPES (%s)", account.label)
        logger.warning(sep)
        logger.warning("The live API check for '%s' returned HTTP 403 Forbidden.", account.label)
        logger.warning("That client's Private Integration Token does not have the")
        logger.warning("required API scopes.")
        logger.warning("")
        logger.warning("To fix this:")
        logger.warning("  1. Log in to GoHighLevel as that client's sub-account")
        logger.warning("  2. Go to Settings → Private Integrations")
        logger.warning("  3. Find your integration and click 'Edit'")
        logger.warning("  4. Enable all required scopes (see INSTALL.md for the")
        logger.warning("     full list) and save")
        logger.warning("  5. Regenerate the token, copy the new 'pit-' value, and")
        logger.warning("     update this client's entry in GHL_CLIENTS")
        logger.warning("  6. Restart Claude Desktop / Claude Code")
        logger.warning("")
        logger.warning("The server will start but calls for this client may fail")
        logger.warning("with permission errors until the scopes are corrected.")
        logger.warning(sep)
    else:
        logger.debug(
            "PIT pre-flight check for %s returned HTTP %s — non-blocking, server will start normally.",
            account.label, status_code,
        )


def _auto_detect_company_id(logger: logging.Logger, body: bytes) -> None:
    """Read ``companyId`` from a location response and record it.

    Every location record carries its parent company ID. No tool in this
    build currently needs it, but it's cheap to capture at DEBUG level in
    case a future client-safe tool wants it — nothing here is user-facing.

    Best-effort: any parse problem is logged at DEBUG and ignored — a failure
    here must never prevent the server from starting.
    """
    try:
        payload = json.loads(body or b"{}")
    except (ValueError, TypeError) as exc:
        logger.debug("Could not parse location response for company ID: %s", exc)
        return

    location = payload.get("location", payload) if isinstance(payload, dict) else {}
    company_id = location.get("companyId") if isinstance(location, dict) else None
    if not company_id:
        logger.debug("Location response did not contain a companyId.")
        return

    if settings.company_id:
        # User pinned an explicit value; respect it, just note any mismatch.
        if settings.company_id != company_id:
            logger.debug(
                "GHL_COMPANY_ID is set to %s but the location belongs to %s — using the configured value.",
                settings.company_id, company_id,
            )
        return

    set_resolved_company_id(company_id)
    logger.debug("Company ID auto-detected from your location: %s", company_id)


def _check_credentials(logger: logging.Logger) -> None:
    """Warn to stderr if no clients are configured, with setup instructions."""
    if settings.clients:
        return

    sep = "=" * 60
    logger.warning(sep)
    logger.warning("GoHighLevel MCP — MISSING CREDENTIALS")
    logger.warning(sep)
    logger.warning("No clients are configured — neither GHL_CLIENTS nor the legacy")
    logger.warning("GHL_API_KEY / GHL_LOCATION_ID pair are set.")
    logger.warning("")
    logger.warning("The server will start but all tool calls will fail until at")
    logger.warning("least one client is configured. Here's how:")
    logger.warning("")
    logger.warning("  Single client — set both:")
    logger.warning('    "GHL_API_KEY": "pit-your-token-here",')
    logger.warning('    "GHL_LOCATION_ID": "your-location-id-here"')
    logger.warning("")
    logger.warning("  Multiple clients — set GHL_CLIENTS to a JSON map:")
    logger.warning('    "GHL_CLIENTS": \'{"loc-id-1": {"api_key": "pit-...", "label": "Client A"}, ')
    logger.warning('                      "loc-id-2": {"api_key": "pit-...", "label": "Client B"}}\'')
    logger.warning("")
    logger.warning("Each PIT is generated per-client at:")
    logger.warning("  GoHighLevel → Settings → Private Integrations (as that client's sub-account)")
    logger.warning("")
    logger.warning("Add these to the 'env' block in your Claude Desktop config:")
    logger.warning("  Mac:     ~/Library/Application Support/Claude/claude_desktop_config.json")
    logger.warning("  Windows: %%APPDATA%%\\Claude\\claude_desktop_config.json")
    logger.warning("")
    logger.warning("Then restart Claude Desktop / Claude Code.")
    logger.warning(sep)


if __name__ == "__main__":
    main()
