"""CLI entrypoint: ``python -m ghl_mcp``."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import urllib.error
import urllib.request

from ghl_mcp.client import USER_AGENT
from ghl_mcp.config import set_resolved_company_id, settings
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
    asyncio.run(_check_token_live(logger))

    logger.info("Starting GoHighLevel MCP server v2.0.0 (location_id=%s)", settings.location_id or "unset")

    mcp.run()


async def _check_token_live(logger: logging.Logger) -> None:
    """Make a lightweight live API call to verify the PIT is valid.

    Uses GET /locations/{location_id} — cheap, unambiguous, requires a working
    token. Only runs when both credentials are present (i.e. after
    _check_credentials has already confirmed they are set).

    On success (200) it also reads ``companyId`` from the location record and
    records it via :func:`set_resolved_company_id`, so agency tools work without
    the user having to find their Agency ID by hand.

    * 200 → token valid; auto-detect and stash the company ID.
    * 401 → token expired or invalid; log a clear remediation banner.
    * 403 → token present but missing required scopes; log a scopes banner.
    * Anything else (4xx other, 5xx, network error) → DEBUG only; never
      blocks startup so that transient network hiccups don't prevent the server
      from starting.
    """
    if not settings.api_key or not settings.location_id:
        # Credentials are missing — _check_credentials already warned; skip.
        return

    url = f"{settings.base_url}/locations/{settings.location_id}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {settings.api_key}",
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
            logger.debug("PIT pre-flight check passed (HTTP 2xx from /locations/%s)", settings.location_id)
            _auto_detect_company_id(logger, resp.read())
            return
    except urllib.error.HTTPError as exc:
        status_code = exc.code
    except Exception as exc:  # noqa: BLE001 — network errors, DNS failures, etc.
        logger.debug("PIT pre-flight check skipped (network error: %s)", exc)
        return

    if status_code == 401:
        logger.warning(sep)
        logger.warning("GoHighLevel MCP — TOKEN EXPIRED OR INVALID")
        logger.warning(sep)
        logger.warning("The live API check returned HTTP 401 Unauthorized.")
        logger.warning("Your Private Integration Token (PIT) is either expired")
        logger.warning("or has been revoked.")
        logger.warning("")
        logger.warning("Private Integration Tokens expire after 90 days of non-use.")
        logger.warning("")
        logger.warning("To regenerate your token:")
        logger.warning("  1. Log in to GoHighLevel")
        logger.warning("  2. Go to Settings → Private Integrations")
        logger.warning("  3. Find your integration and click 'Regenerate Token'")
        logger.warning("     (or create a new integration if needed)")
        logger.warning("  4. Copy the new token — it starts with 'pit-'")
        logger.warning("  5. Update GHL_API_KEY in your Claude Desktop config:")
        logger.warning("       Mac:     ~/Library/Application Support/Claude/claude_desktop_config.json")
        logger.warning("       Windows: %%APPDATA%%\\Claude\\claude_desktop_config.json")
        logger.warning("  6. Restart Claude Desktop")
        logger.warning("")
        logger.warning("The server will start but all tool calls will fail until")
        logger.warning("the token is replaced.")
        logger.warning(sep)
    elif status_code == 403:
        logger.warning(sep)
        logger.warning("GoHighLevel MCP — TOKEN HAS INSUFFICIENT SCOPES")
        logger.warning(sep)
        logger.warning("The live API check returned HTTP 403 Forbidden.")
        logger.warning("Your Private Integration Token does not have the required")
        logger.warning("API scopes to access this location.")
        logger.warning("")
        logger.warning("To fix this:")
        logger.warning("  1. Log in to GoHighLevel")
        logger.warning("  2. Go to Settings → Private Integrations")
        logger.warning("  3. Find your integration and click 'Edit'")
        logger.warning("  4. Enable all required scopes (see INSTALL.md for the")
        logger.warning("     full list) and save")
        logger.warning("  5. Regenerate the token, copy the new 'pit-' value")
        logger.warning("  6. Update GHL_API_KEY in your Claude Desktop config and")
        logger.warning("     restart Claude Desktop")
        logger.warning("")
        logger.warning("The server will start but tool calls may fail with")
        logger.warning("permission errors until the scopes are corrected.")
        logger.warning(sep)
    else:
        logger.debug(
            "PIT pre-flight check returned HTTP %s — non-blocking, server will start normally.",
            status_code,
        )


def _auto_detect_company_id(logger: logging.Logger, body: bytes) -> None:
    """Read ``companyId`` from a location response and record it.

    The location record returned by GET /locations/{id} carries the agency's
    company ID, so agency owners never need to look it up manually. If the user
    has set GHL_COMPANY_ID explicitly, that takes precedence and we only log;
    otherwise the detected value becomes the fallback used by agency tools.

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
            logger.info(
                "GHL_COMPANY_ID is set to %s but the location belongs to agency %s — using the configured value.",
                settings.company_id, company_id,
            )
        return

    set_resolved_company_id(company_id)
    logger.info(
        "Agency/company ID auto-detected from your location: %s "
        "(agency tools are enabled; set GHL_COMPANY_ID to pin this value).",
        company_id,
    )


def _check_credentials(logger: logging.Logger) -> None:
    """Warn to stderr if required credentials are missing, with setup instructions."""
    missing = []
    if not settings.api_key:
        missing.append("GHL_API_KEY")
    if not settings.location_id:
        missing.append("GHL_LOCATION_ID")

    if not missing:
        # Both required credentials are present. GHL_COMPANY_ID is optional —
        # if unset, the live pre-flight check below auto-detects it from the
        # location, so agency tools still work. Don't warn here.
        if not settings.company_id:
            logger.info(
                "GHL_COMPANY_ID not set — it will be auto-detected from your location at startup. "
                "Set it in your config env block only if you want to pin a specific agency."
            )
        return

    sep = "=" * 60
    logger.warning(sep)
    logger.warning("GoHighLevel MCP — MISSING CREDENTIALS")
    logger.warning(sep)
    logger.warning("The following environment variables are not set: %s", ", ".join(missing))
    logger.warning("")
    logger.warning("The server will start but all tool calls will fail until")
    logger.warning("these are configured. Here's how to get them:")
    logger.warning("")
    if "GHL_API_KEY" in missing:
        logger.warning("  GHL_API_KEY (Private Integration Token):")
        logger.warning("    1. Log in to GoHighLevel")
        logger.warning("    2. Go to Settings → Private Integrations")
        logger.warning("    3. Click 'Create new Integration'")
        logger.warning("    4. Enable the required scopes (see INSTALL.md)")
        logger.warning("    5. Copy the token — it starts with 'pit-'")
        logger.warning("")
    if "GHL_LOCATION_ID" in missing:
        logger.warning("  GHL_LOCATION_ID (Sub-Account / Location ID):")
        logger.warning("    1. Log in to GoHighLevel")
        logger.warning("    2. Go to Settings → Business Profile")
        logger.warning("    3. Copy the Location ID from the page or URL")
        logger.warning("")
    logger.warning("Add these to the 'env' block in your Claude Desktop config:")
    logger.warning("  Mac:     ~/Library/Application Support/Claude/claude_desktop_config.json")
    logger.warning("  Windows: %%APPDATA%%\\Claude\\claude_desktop_config.json")
    logger.warning("")
    logger.warning('  "env": {')
    logger.warning('    "GHL_API_KEY": "pit-your-token-here",')
    logger.warning('    "GHL_LOCATION_ID": "your-location-id-here"')
    logger.warning('  }')
    logger.warning("")
    logger.warning("Then restart Claude Desktop.")
    logger.warning(sep)


if __name__ == "__main__":
    main()
