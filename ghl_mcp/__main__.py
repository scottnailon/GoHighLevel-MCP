"""CLI entrypoint: ``python -m ghl_mcp``."""

from __future__ import annotations

import asyncio
import logging
import sys
import urllib.error
import urllib.request

from ghl_mcp.config import settings
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

    * 401 → token expired or invalid; log a clear remediation banner.
    * 403 → token present but missing required scopes; log a scopes banner.
    * Anything else (200, 4xx other, 5xx, network error) → DEBUG only; never
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
        },
        method="GET",
    )

    sep = "=" * 60
    status_code: int | None = None

    try:
        # Run the blocking urllib call in a thread so we stay async-friendly.
        loop = asyncio.get_running_loop()
        with await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=10)) as _resp:
            # 2xx — token is valid; nothing to warn about.
            logger.debug("PIT pre-flight check passed (HTTP 2xx from /locations/%s)", settings.location_id)
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


def _check_credentials(logger: logging.Logger) -> None:
    """Warn to stderr if required credentials are missing, with setup instructions."""
    missing = []
    if not settings.api_key:
        missing.append("GHL_API_KEY")
    if not settings.location_id:
        missing.append("GHL_LOCATION_ID")

    if not missing:
        # Both required credentials are present — check for optional agency credential.
        if not settings.company_id:
            logger.info(
                "GHL_COMPANY_ID not set — agency tools (snapshots, SaaS, sub-accounts, companies) "
                "will be unavailable. Set it in your Claude Desktop config env block if needed."
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
