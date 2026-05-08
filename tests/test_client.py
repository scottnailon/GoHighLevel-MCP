"""Unit tests for the GHL HTTP client.

Uses ``respx`` to mock httpx requests without touching the live API.
Run with: ``pytest tests/test_client.py -v``
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from ghl_mcp.client import GHLClient
from ghl_mcp.errors import (
    GHLAuthError,
    GHLNotFoundError,
    GHLRateLimitError,
    GHLValidationError,
)


@pytest.fixture
def client() -> GHLClient:
    return GHLClient(
        api_key="test-token-pit-fake",
        base_url="https://services.leadconnectorhq.com",
        api_version="2021-07-28",
        max_retries=0,
    )


@respx.mock
@pytest.mark.asyncio
async def test_get_success(client: GHLClient) -> None:
    """A 200 response returns parsed JSON."""
    respx.get("https://services.leadconnectorhq.com/contacts/").mock(
        return_value=Response(200, json={"contacts": [{"id": "c1"}]})
    )
    result = await client.get("/contacts/")
    assert result == {"contacts": [{"id": "c1"}]}
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_401_raises_auth_error(client: GHLClient) -> None:
    """401 maps to GHLAuthError with token-rotation hint."""
    respx.get("https://services.leadconnectorhq.com/contacts/").mock(
        return_value=Response(401, json={"message": "invalid token"})
    )
    with pytest.raises(GHLAuthError) as excinfo:
        await client.get("/contacts/")
    assert "expire" in str(excinfo.value).lower() or "scope" in str(excinfo.value).lower()
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_404_raises_not_found(client: GHLClient) -> None:
    respx.get("https://services.leadconnectorhq.com/contacts/missing").mock(
        return_value=Response(404, json={"message": "not found"})
    )
    with pytest.raises(GHLNotFoundError):
        await client.get("/contacts/missing")
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_422_raises_validation_error(client: GHLClient) -> None:
    respx.post("https://services.leadconnectorhq.com/contacts/").mock(
        return_value=Response(422, json={"message": "email required"})
    )
    with pytest.raises(GHLValidationError):
        await client.post("/contacts/", json={})
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_429_with_no_retries_raises(client: GHLClient) -> None:
    """When max_retries=0, 429 surfaces immediately as a typed error."""
    respx.get("https://services.leadconnectorhq.com/contacts/").mock(
        return_value=Response(429, json={"message": "rate limited"})
    )
    with pytest.raises(GHLRateLimitError):
        await client.get("/contacts/")
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_none_params_stripped(client: GHLClient) -> None:
    """Request params with None values are removed before sending."""
    route = respx.get("https://services.leadconnectorhq.com/contacts/").mock(
        return_value=Response(200, json={})
    )
    await client.get("/contacts/", params={"keep": "yes", "drop": None})
    sent_url = str(route.calls[0].request.url)
    assert "keep=yes" in sent_url
    assert "drop" not in sent_url
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_204_returns_empty_dict(client: GHLClient) -> None:
    """204 No Content responses return an empty dict instead of breaking JSON parse."""
    respx.delete("https://services.leadconnectorhq.com/contacts/c1").mock(
        return_value=Response(204)
    )
    result = await client.delete("/contacts/c1")
    assert result == {}
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_authorization_header_set(client: GHLClient) -> None:
    """Every request carries the bearer token and version header."""
    route = respx.get("https://services.leadconnectorhq.com/anything").mock(
        return_value=Response(200, json={})
    )
    await client.get("/anything")
    headers = route.calls[0].request.headers
    assert headers["authorization"] == "Bearer test-token-pit-fake"
    assert headers["version"] == "2021-07-28"
    await client.close()
