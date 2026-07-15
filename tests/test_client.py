"""Unit tests for the GHL HTTP client.

Uses ``respx`` to mock httpx requests without touching the live API.
Run with: ``pytest tests/test_client.py -v``
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response

import ghl_mcp.client as client_module
from ghl_mcp.client import GHLClient
from ghl_mcp.config import ClientAccount, Settings
from ghl_mcp.errors import (
    GHLAuthError,
    GHLNotFoundError,
    GHLRateLimitError,
    GHLValidationError,
)


@pytest.fixture(autouse=True)
def _single_client_configured(monkeypatch):
    """Every test in this file gets one configured client by default, so
    resolve_client() with no location_id just works — matching the common
    single-client setup. Tests needing multiple clients override explicitly."""
    account = ClientAccount(location_id="loc-test", api_key="test-token-pit-fake", label="Test Client")
    settings = Settings(clients={"loc-test": account})
    monkeypatch.setattr(client_module, "settings", settings)
    return settings


@pytest.fixture
def client() -> GHLClient:
    return GHLClient(
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


# ---------------------------------------------------------------------------
# Multi-client token selection
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_explicit_location_id_selects_matching_client(client: GHLClient, monkeypatch) -> None:
    accounts = {
        "loc-a": ClientAccount(location_id="loc-a", api_key="pit-a", label="Client A"),
        "loc-b": ClientAccount(location_id="loc-b", api_key="pit-b", label="Client B"),
    }
    monkeypatch.setattr(client_module, "settings", Settings(clients=accounts))

    route = respx.get("https://services.leadconnectorhq.com/contacts/").mock(
        return_value=Response(200, json={})
    )
    await client.get("/contacts/", location_id="loc-b")
    assert route.calls[0].request.headers["authorization"] == "Bearer pit-b"
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_unknown_location_id_raises_before_request(client: GHLClient, monkeypatch) -> None:
    accounts = {"loc-a": ClientAccount(location_id="loc-a", api_key="pit-a", label="Client A")}
    monkeypatch.setattr(client_module, "settings", Settings(clients=accounts))

    route = respx.get("https://services.leadconnectorhq.com/contacts/").mock(
        return_value=Response(200, json={})
    )
    with pytest.raises(ValueError, match="Unknown location_id"):
        await client.get("/contacts/", location_id="loc-nonexistent")
    assert route.call_count == 0  # never sent — fails closed, not open
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_no_location_id_uses_default(client: GHLClient, monkeypatch) -> None:
    accounts = {
        "loc-a": ClientAccount(location_id="loc-a", api_key="pit-a", label="Client A"),
        "loc-b": ClientAccount(location_id="loc-b", api_key="pit-b", label="Client B"),
    }
    monkeypatch.setattr(client_module, "settings", Settings(clients=accounts, default_location_id="loc-b"))

    route = respx.get("https://services.leadconnectorhq.com/contacts/").mock(
        return_value=Response(200, json={})
    )
    await client.get("/contacts/")
    assert route.calls[0].request.headers["authorization"] == "Bearer pit-b"
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_multiple_clients_no_location_no_default_raises(client: GHLClient, monkeypatch) -> None:
    accounts = {
        "loc-a": ClientAccount(location_id="loc-a", api_key="pit-a", label="Client A"),
        "loc-b": ClientAccount(location_id="loc-b", api_key="pit-b", label="Client B"),
    }
    monkeypatch.setattr(client_module, "settings", Settings(clients=accounts))

    route = respx.get("https://services.leadconnectorhq.com/contacts/").mock(
        return_value=Response(200, json={})
    )
    with pytest.raises(ValueError, match="Multiple clients configured"):
        await client.get("/contacts/")
    assert route.call_count == 0
    await client.close()
