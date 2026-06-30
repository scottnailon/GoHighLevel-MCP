"""Async HTTP client for the GoHighLevel API.

Single source of truth for:
- Authentication (Private Integration Token in Authorization header)
- API version pinning
- Rate-limit awareness (reads X-RateLimit-* response headers)
- Exponential-backoff retry on 429 and transient 5xx
- Mapping HTTP errors to typed exceptions
- Optional structured logging of every request
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from ghl_mcp import __version__
from ghl_mcp.config import settings
from ghl_mcp.errors import GHLTimeoutError, map_status_to_exception

logger = logging.getLogger("ghl_mcp.client")

# GHL is fronted by Cloudflare, which rejects requests carrying the default
# Python User-Agent (HTTP 403, Error 1010). Always send an explicit UA.
USER_AGENT = f"ghl-mcp/{__version__}"


class GHLClient:
    """Async HTTP client wrapping the GHL V2 API.

    Designed to be reused across many tool calls. Tools should use the
    module-level :func:`get_client` / context manager pattern rather than
    instantiating directly.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        api_version: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ):
        self._api_key = api_key or settings.require_api_key()
        self._base_url = (base_url or settings.base_url).rstrip("/")
        self._api_version = api_version or settings.api_version
        self._timeout = timeout if timeout is not None else settings.timeout
        self._max_retries = max_retries if max_retries is not None else settings.max_retries
        self._client: httpx.AsyncClient | None = None

    # ---------------------------------------------------------------
    # Lifecycle
    # ---------------------------------------------------------------

    async def __aenter__(self) -> GHLClient:
        await self._open()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    async def _open(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                headers=self._default_headers(),
            )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _default_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Version": self._api_version,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }

    # ---------------------------------------------------------------
    # Core request
    # ---------------------------------------------------------------

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any] | list[Any]:
        """Make an HTTP request and return parsed JSON.

        Retries on 429 and 5xx with exponential backoff (2^attempt seconds,
        capped at 30s). Raises typed :class:`GHLError` on non-recoverable
        failure.
        """
        await self._open()
        assert self._client is not None  # for type checkers

        # Strip None values from params — httpx encodes them as the literal
        # string "None" otherwise.
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}

        last_exception: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.request(
                    method,
                    path,
                    params=clean_params or None,
                    json=json,
                    files=files,
                    headers=extra_headers,
                )
            except httpx.TimeoutException as exc:
                last_exception = exc
                logger.warning("Timeout on %s %s (attempt %d)", method, path, attempt + 1)
                if attempt < self._max_retries:
                    await asyncio.sleep(min(2**attempt, 30))
                    continue
                raise GHLTimeoutError(f"Request timed out: {method} {path}") from exc
            except httpx.HTTPError as exc:
                # Connection errors, etc — don't retry.
                logger.error("HTTP error on %s %s: %s", method, path, exc)
                raise map_status_to_exception(0, f"HTTP error: {exc}") from exc

            # Surface rate-limit telemetry to the logs for visibility.
            self._log_rate_limit_headers(response)

            if response.status_code == 429:
                if attempt < self._max_retries:
                    retry_after = int(response.headers.get("Retry-After", "0") or 0)
                    delay = retry_after if retry_after > 0 else min(2**attempt, 30)
                    logger.warning(
                        "Rate limited on %s %s, sleeping %ss (attempt %d)",
                        method, path, delay, attempt + 1,
                    )
                    await asyncio.sleep(delay)
                    continue

            if 500 <= response.status_code < 600:
                if attempt < self._max_retries:
                    delay = min(2**attempt, 30)
                    logger.warning(
                        "Server error %d on %s %s, retrying in %ss",
                        response.status_code, method, path, delay,
                    )
                    await asyncio.sleep(delay)
                    continue

            if response.status_code >= 400:
                raise map_status_to_exception(
                    response.status_code,
                    f"GHL API error ({response.status_code}) on {method} {path}",
                    details=self._extract_error_detail(response),
                )

            # Success — parse JSON. Tolerate empty 204 responses.
            if response.status_code == 204 or not response.content:
                return {}
            try:
                return response.json()
            except ValueError as exc:
                raise map_status_to_exception(
                    response.status_code,
                    "GHL returned non-JSON response",
                    details=response.text[:500],
                ) from exc

        # Should never reach here — every retry path either continues, returns,
        # or raises. This is defensive.
        if last_exception:
            raise GHLTimeoutError("Max retries exceeded") from last_exception
        raise GHLTimeoutError("Max retries exceeded")

    # ---------------------------------------------------------------
    # Convenience verbs
    # ---------------------------------------------------------------

    async def get(self, path: str, **kwargs: Any) -> Any:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> Any:
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> Any:
        return await self.request("PUT", path, **kwargs)

    async def patch(self, path: str, **kwargs: Any) -> Any:
        return await self.request("PATCH", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> Any:
        return await self.request("DELETE", path, **kwargs)

    # ---------------------------------------------------------------
    # Internals
    # ---------------------------------------------------------------

    @staticmethod
    def _log_rate_limit_headers(response: httpx.Response) -> None:
        """Log GHL's rate-limit headers if present."""
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is not None:
            try:
                remaining_int = int(remaining)
            except ValueError:
                return
            if remaining_int < 10:
                logger.warning("GHL rate limit nearly exhausted: %s remaining", remaining)
            elif remaining_int < 25:
                logger.info("GHL rate limit getting tight: %s remaining", remaining)

    @staticmethod
    def _extract_error_detail(response: httpx.Response) -> str:
        """Pull a useful detail string out of an error response."""
        try:
            body = response.json()
        except ValueError:
            return response.text[:500]

        if isinstance(body, dict):
            for key in ("message", "error", "msg", "detail"):
                if key in body and isinstance(body[key], str):
                    return body[key]
            return str(body)[:500]
        return str(body)[:500]


# ---------------------------------------------------------------
# Module-level singleton helper
# ---------------------------------------------------------------

_singleton_client: GHLClient | None = None


async def get_client() -> GHLClient:
    """Return a process-wide :class:`GHLClient` singleton.

    Connections are reused for the lifetime of the MCP server, which keeps
    httpx's connection pool warm across many tool calls.
    """
    global _singleton_client
    if _singleton_client is None:
        _singleton_client = GHLClient()
        await _singleton_client._open()
    return _singleton_client


async def close_client() -> None:
    """Close the singleton client. Called on server shutdown."""
    global _singleton_client
    if _singleton_client is not None:
        await _singleton_client.close()
        _singleton_client = None
