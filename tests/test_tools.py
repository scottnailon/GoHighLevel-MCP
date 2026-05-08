"""Integration tests for GHL tool functions.

Uses ``respx`` to mock httpx at the HTTP layer — no live API calls, no patching
of the GHL client methods. The tools are exercised end-to-end through the same
code path they use in production (get_client → GHLClient → httpx).

Run with: ``pytest tests/test_tools.py -v``
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import respx
from httpx import Response

from ghl_mcp.client import GHLClient
from ghl_mcp.errors import GHLAuthError, GHLNotFoundError, GHLValidationError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://services.leadconnectorhq.com"
API_KEY = "test-key"
LOCATION_ID = "test-loc"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ghl_client() -> GHLClient:
    """A GHLClient wired to the test base URL with no retries."""
    return GHLClient(
        api_key=API_KEY,
        base_url=BASE_URL,
        api_version="2021-07-28",
        max_retries=0,
    )


@pytest.fixture(autouse=True)
def patch_get_client(ghl_client: GHLClient):
    """Replace the module-level get_client() singleton with our test client.

    Applies to every test in this module automatically.  Each tool module
    imports ``get_client`` from ``ghl_mcp.client``, so we patch it there.
    """
    async def _get_client() -> GHLClient:
        return ghl_client

    targets = [
        "ghl_mcp.tools.contacts.get_client",
        "ghl_mcp.tools.opportunities.get_client",
        "ghl_mcp.tools.messaging.get_client",
        "ghl_mcp.tools.calendars.get_client",
    ]
    patchers = [patch(t, side_effect=_get_client) for t in targets]
    for p in patchers:
        p.start()
    yield
    for p in patchers:
        p.stop()


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch):
    """Override the module-level settings singleton for every test."""
    monkeypatch.setenv("GHL_API_KEY", API_KEY)
    monkeypatch.setenv("GHL_LOCATION_ID", LOCATION_ID)
    # Reload settings so the tools see the patched env vars.
    import ghl_mcp.config as cfg
    cfg.settings = cfg._load_settings()
    yield
    # Restore to avoid leaking state — _load_settings() reads os.environ which
    # monkeypatch already restores, so we just reload once more after teardown.
    cfg.settings = cfg._load_settings()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _contact(id: str = "c1", first: str = "Alice", last: str = "Smith") -> dict[str, Any]:
    return {
        "id": id,
        "firstName": first,
        "lastName": last,
        "email": f"{first.lower()}@example.com",
        "phone": "+61400000001",
        "tags": ["vip"],
        "dateAdded": "2026-01-15T10:00:00Z",
        "dateUpdated": "2026-03-01T12:00:00Z",
        "source": "website",
    }


def _opportunity(id: str = "opp1") -> dict[str, Any]:
    return {
        "id": id,
        "name": "Big Deal",
        "monetaryValue": 5000,
        "status": "open",
        "pipelineId": "pipe1",
        "pipelineStageId": "stage1",
        "contactId": "c1",
    }


# ===========================================================================
# CONTACTS
# ===========================================================================


@respx.mock
@pytest.mark.asyncio
async def test_contacts_list_success_json() -> None:
    """List contacts returns valid pagination envelope in JSON format."""
    from ghl_mcp.tools.contacts import ContactsListInput

    contacts = [_contact("c1"), _contact("c2", "Bob", "Jones")]
    respx.get(f"{BASE_URL}/contacts/").mock(
        return_value=Response(200, json={"contacts": contacts, "total": 2})
    )

    input_data = ContactsListInput(location_id=LOCATION_ID, response_format="json")

    # Call the underlying async function directly by re-registering on a mock.
    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):  # noqa: ANN001
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.contacts as contacts_mod
    fake = _FakeMCP()
    contacts_mod.register(fake)

    # The first registered tool is ghl_contacts_list.
    fn = _calls[0]
    result = await fn(input_data)

    data = json.loads(result)
    assert data["count"] == 2
    assert data["total"] == 2
    assert data["has_more"] is False
    assert data["next_skip"] is None
    assert len(data["contacts"]) == 2


@respx.mock
@pytest.mark.asyncio
async def test_contacts_list_success_markdown() -> None:
    """List contacts in markdown format produces a table and pagination footer."""
    contacts = [_contact("c1")]
    respx.get(f"{BASE_URL}/contacts/").mock(
        return_value=Response(200, json={"contacts": contacts, "total": 1})
    )

    from ghl_mcp.tools.contacts import ContactsListInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.contacts as contacts_mod
    fake = _FakeMCP()
    contacts_mod.register(fake)

    fn = _calls[0]
    result = await fn(ContactsListInput(location_id=LOCATION_ID, response_format="markdown"))

    assert "| ID |" in result or "ID" in result
    assert "Alice" in result
    assert "Showing" in result


@respx.mock
@pytest.mark.asyncio
async def test_contacts_list_empty_result() -> None:
    """Empty contacts list returns zero count and no next_skip."""
    respx.get(f"{BASE_URL}/contacts/").mock(
        return_value=Response(200, json={"contacts": [], "total": 0})
    )

    from ghl_mcp.tools.contacts import ContactsListInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.contacts as contacts_mod
    contacts_mod.register(_FakeMCP())
    fn = _calls[0]

    result = await fn(ContactsListInput(location_id=LOCATION_ID, response_format="json"))
    data = json.loads(result)
    assert data["count"] == 0
    assert data["has_more"] is False
    assert data["next_skip"] is None


@respx.mock
@pytest.mark.asyncio
async def test_contacts_list_pagination_metadata() -> None:
    """Pagination metadata (has_more, next_skip) is correct for partial pages."""
    contacts = [_contact(f"c{i}") for i in range(20)]  # full page of 20
    respx.get(f"{BASE_URL}/contacts/").mock(
        return_value=Response(200, json={"contacts": contacts, "total": 45})
    )

    from ghl_mcp.tools.contacts import ContactsListInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.contacts as contacts_mod
    contacts_mod.register(_FakeMCP())
    fn = _calls[0]

    result = await fn(ContactsListInput(location_id=LOCATION_ID, limit=20, skip=0, response_format="json"))
    data = json.loads(result)
    assert data["count"] == 20
    assert data["total"] == 45
    assert data["has_more"] is True
    assert data["next_skip"] == 20
    assert data["skip"] == 0
    assert data["limit"] == 20


@respx.mock
@pytest.mark.asyncio
async def test_contacts_get_success() -> None:
    """Get contact by ID returns the contact detail."""
    contact = _contact("c42")
    respx.get(f"{BASE_URL}/contacts/c42").mock(
        return_value=Response(200, json={"contact": contact})
    )

    from ghl_mcp.tools.contacts import ContactGetInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.contacts as contacts_mod
    contacts_mod.register(_FakeMCP())
    # ghl_contacts_get is the second registered tool.
    fn = _calls[1]

    result = await fn(ContactGetInput(contact_id="c42", response_format="json"))
    data = json.loads(result)
    assert data["id"] == "c42"
    assert data["firstName"] == "Alice"


@respx.mock
@pytest.mark.asyncio
async def test_contacts_get_404_raises() -> None:
    """A 404 from GHL surfaces as GHLNotFoundError (not a raw exception)."""
    respx.get(f"{BASE_URL}/contacts/missing").mock(
        return_value=Response(404, json={"message": "contact not found"})
    )

    from ghl_mcp.tools.contacts import ContactGetInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.contacts as contacts_mod
    contacts_mod.register(_FakeMCP())
    fn = _calls[1]  # ghl_contacts_get

    with pytest.raises(GHLNotFoundError):
        await fn(ContactGetInput(contact_id="missing", response_format="json"))


@respx.mock
@pytest.mark.asyncio
async def test_contacts_create_success() -> None:
    """Create contact returns the created contact payload."""
    new_contact = _contact("c99", "New", "Person")
    respx.post(f"{BASE_URL}/contacts/").mock(
        return_value=Response(200, json={"contact": new_contact})
    )

    from ghl_mcp.tools.contacts import ContactCreateInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.contacts as contacts_mod
    contacts_mod.register(_FakeMCP())
    fn = _calls[2]  # ghl_contacts_create

    result = await fn(ContactCreateInput(
        location_id=LOCATION_ID,
        first_name="New",
        last_name="Person",
        email="new@example.com",
    ))
    # result is formatted JSON or markdown — either way it must not be an error string
    assert "c99" in result or "New" in result


@respx.mock
@pytest.mark.asyncio
async def test_contacts_create_validation_error() -> None:
    """A 422 from GHL during contact creation raises GHLValidationError."""
    respx.post(f"{BASE_URL}/contacts/").mock(
        return_value=Response(422, json={"message": "email is invalid"})
    )

    from ghl_mcp.tools.contacts import ContactCreateInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.contacts as contacts_mod
    contacts_mod.register(_FakeMCP())
    fn = _calls[2]  # ghl_contacts_create

    with pytest.raises(GHLValidationError):
        await fn(ContactCreateInput(
            location_id=LOCATION_ID,
            email="not-an-email",
        ))


@respx.mock
@pytest.mark.asyncio
async def test_contacts_401_surfaces_clear_error() -> None:
    """A 401 from GHL raises GHLAuthError with a helpful message, not a raw exception."""
    respx.get(f"{BASE_URL}/contacts/").mock(
        return_value=Response(401, json={"message": "Unauthorized"})
    )

    from ghl_mcp.tools.contacts import ContactsListInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.contacts as contacts_mod
    contacts_mod.register(_FakeMCP())
    fn = _calls[0]

    with pytest.raises(GHLAuthError) as excinfo:
        await fn(ContactsListInput(location_id=LOCATION_ID))
    error_msg = str(excinfo.value).lower()
    # Should mention token expiry or scopes — not just a raw HTTP error.
    assert "expire" in error_msg or "scope" in error_msg or "token" in error_msg


# ===========================================================================
# OPPORTUNITIES
# ===========================================================================


@respx.mock
@pytest.mark.asyncio
async def test_opportunities_list_success() -> None:
    """List opportunities returns pagination envelope with opportunities key."""
    opps = [_opportunity("opp1"), _opportunity("opp2")]
    respx.get(f"{BASE_URL}/opportunities/search").mock(
        return_value=Response(200, json={"opportunities": opps, "total": 2})
    )

    from ghl_mcp.tools.opportunities import OpportunitiesListInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.opportunities as opps_mod
    opps_mod.register(_FakeMCP())
    fn = _calls[0]  # ghl_opportunities_list

    result = await fn(OpportunitiesListInput(location_id=LOCATION_ID, response_format="json"))
    data = json.loads(result)
    assert data["count"] == 2
    assert data["total"] == 2
    assert data["has_more"] is False
    assert len(data["opportunities"]) == 2


@respx.mock
@pytest.mark.asyncio
async def test_opportunities_list_pagination_metadata() -> None:
    """Pagination metadata is correct for a paginated opportunities list."""
    opps = [_opportunity(f"opp{i}") for i in range(10)]
    respx.get(f"{BASE_URL}/opportunities/search").mock(
        return_value=Response(200, json={"opportunities": opps, "total": 35})
    )

    from ghl_mcp.tools.opportunities import OpportunitiesListInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.opportunities as opps_mod
    opps_mod.register(_FakeMCP())
    fn = _calls[0]

    result = await fn(OpportunitiesListInput(
        location_id=LOCATION_ID, limit=10, skip=0, response_format="json"
    ))
    data = json.loads(result)
    assert data["count"] == 10
    assert data["total"] == 35
    assert data["has_more"] is True
    assert data["next_skip"] == 10


@respx.mock
@pytest.mark.asyncio
async def test_opportunities_move_stage_success() -> None:
    """Move opportunity to a new stage sends PUT to the correct endpoint."""
    updated = {**_opportunity("opp1"), "pipelineStageId": "stage2"}
    route = respx.put(f"{BASE_URL}/opportunities/opp1").mock(
        return_value=Response(200, json=updated)
    )

    from ghl_mcp.tools.opportunities import OpportunityMoveStageInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.opportunities as opps_mod
    opps_mod.register(_FakeMCP())
    # Tool order: list, get, create, update, delete, move_stage, update_status, search
    fn = _calls[5]  # ghl_opportunities_move_stage

    result = await fn(OpportunityMoveStageInput(
        opportunity_id="opp1",
        pipeline_stage_id="stage2",
    ))
    data = json.loads(result)
    assert data["pipelineStageId"] == "stage2"
    # Verify the request body was correct.
    body = json.loads(route.calls[0].request.content)
    assert body["pipelineStageId"] == "stage2"


@respx.mock
@pytest.mark.asyncio
async def test_opportunities_update_status_success() -> None:
    """Update opportunity status sends PUT to the /status sub-resource."""
    updated = {**_opportunity("opp1"), "status": "won"}
    route = respx.put(f"{BASE_URL}/opportunities/opp1/status").mock(
        return_value=Response(200, json=updated)
    )

    from ghl_mcp.tools.opportunities import OpportunityUpdateStatusInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.opportunities as opps_mod
    opps_mod.register(_FakeMCP())
    fn = _calls[6]  # ghl_opportunities_update_status

    result = await fn(OpportunityUpdateStatusInput(
        opportunity_id="opp1",
        status="won",
    ))
    data = json.loads(result)
    assert data["status"] == "won"
    body = json.loads(route.calls[0].request.content)
    assert body["status"] == "won"


@respx.mock
@pytest.mark.asyncio
async def test_opportunities_list_markdown_format() -> None:
    """Opportunities list in markdown format produces a table and footer."""
    opps = [_opportunity("opp1")]
    respx.get(f"{BASE_URL}/opportunities/search").mock(
        return_value=Response(200, json={"opportunities": opps, "total": 1})
    )

    from ghl_mcp.tools.opportunities import OpportunitiesListInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.opportunities as opps_mod
    opps_mod.register(_FakeMCP())
    fn = _calls[0]

    result = await fn(OpportunitiesListInput(location_id=LOCATION_ID, response_format="markdown"))
    assert "Big Deal" in result
    assert "Showing" in result


@respx.mock
@pytest.mark.asyncio
async def test_opportunities_401_surfaces_clear_error() -> None:
    """A 401 on opportunities list raises GHLAuthError with token hint."""
    respx.get(f"{BASE_URL}/opportunities/search").mock(
        return_value=Response(401, json={"message": "Unauthorized"})
    )

    from ghl_mcp.tools.opportunities import OpportunitiesListInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.opportunities as opps_mod
    opps_mod.register(_FakeMCP())
    fn = _calls[0]

    with pytest.raises(GHLAuthError) as excinfo:
        await fn(OpportunitiesListInput(location_id=LOCATION_ID))
    error_msg = str(excinfo.value).lower()
    assert "expire" in error_msg or "scope" in error_msg or "token" in error_msg


# ===========================================================================
# MESSAGING
# ===========================================================================


@respx.mock
@pytest.mark.asyncio
async def test_send_sms_success() -> None:
    """Send SMS posts to /conversations/messages with type=SMS."""
    payload = {"id": "msg1", "status": "sent", "type": "SMS"}
    route = respx.post(f"{BASE_URL}/conversations/messages").mock(
        return_value=Response(200, json=payload)
    )

    from ghl_mcp.tools.messaging import SmsSendInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.messaging as msg_mod
    msg_mod.register(_FakeMCP())
    # Tool order: messages_list, send_sms, send_email, send_whatsapp
    fn = _calls[1]  # ghl_messages_send_sms

    result = await fn(SmsSendInput(
        contact_id="c1",
        message="Hello from test",
    ))
    data = json.loads(result)
    assert data["type"] == "SMS"
    body = json.loads(route.calls[0].request.content)
    assert body["type"] == "SMS"
    assert body["contactId"] == "c1"
    assert body["message"] == "Hello from test"


@respx.mock
@pytest.mark.asyncio
async def test_send_sms_with_from_number() -> None:
    """Optional from_number is included in the SMS request body when provided."""
    route = respx.post(f"{BASE_URL}/conversations/messages").mock(
        return_value=Response(200, json={"id": "msg2", "status": "sent"})
    )

    from ghl_mcp.tools.messaging import SmsSendInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.messaging as msg_mod
    msg_mod.register(_FakeMCP())
    fn = _calls[1]

    await fn(SmsSendInput(
        contact_id="c1",
        message="Hi!",
        from_number="+61400000000",
    ))
    body = json.loads(route.calls[0].request.content)
    assert body["fromNumber"] == "+61400000000"


@respx.mock
@pytest.mark.asyncio
async def test_send_sms_missing_message_rejected_by_pydantic() -> None:
    """Pydantic rejects SMS input when the required 'message' field is absent."""
    from pydantic import ValidationError

    from ghl_mcp.tools.messaging import SmsSendInput

    with pytest.raises(ValidationError):
        SmsSendInput(contact_id="c1")  # message is required


@respx.mock
@pytest.mark.asyncio
async def test_send_sms_401_raises_auth_error() -> None:
    """A 401 during SMS send raises GHLAuthError."""
    respx.post(f"{BASE_URL}/conversations/messages").mock(
        return_value=Response(401, json={"message": "invalid token"})
    )

    from ghl_mcp.tools.messaging import SmsSendInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.messaging as msg_mod
    msg_mod.register(_FakeMCP())
    fn = _calls[1]

    with pytest.raises(GHLAuthError):
        await fn(SmsSendInput(contact_id="c1", message="Hi"))


# ===========================================================================
# CALENDARS
# ===========================================================================


@respx.mock
@pytest.mark.asyncio
async def test_calendars_get_free_slots_success() -> None:
    """Get free calendar slots returns the API payload."""
    slots_payload = {
        "2026-05-10": [
            {"startTime": "09:00", "endTime": "09:30"},
            {"startTime": "10:00", "endTime": "10:30"},
        ],
        "2026-05-11": [
            {"startTime": "14:00", "endTime": "14:30"},
        ],
    }
    respx.get(f"{BASE_URL}/calendars/cal1/free-slots").mock(
        return_value=Response(200, json=slots_payload)
    )

    from ghl_mcp.tools.calendars import CalendarFreeSlotsInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.calendars as cal_mod
    cal_mod.register(_FakeMCP())
    # Tool order: list, get, create, update, delete, get_free_slots
    fn = _calls[5]  # ghl_calendars_get_free_slots

    result = await fn(CalendarFreeSlotsInput(
        calendar_id="cal1",
        start_date="1746835200000",
        end_date="1747008000000",
        response_format="json",
    ))
    data = json.loads(result)
    assert "2026-05-10" in data
    assert len(data["2026-05-10"]) == 2


@respx.mock
@pytest.mark.asyncio
async def test_calendars_get_free_slots_with_timezone() -> None:
    """Timezone param is passed through to the API query string."""
    route = respx.get(f"{BASE_URL}/calendars/cal1/free-slots").mock(
        return_value=Response(200, json={})
    )

    from ghl_mcp.tools.calendars import CalendarFreeSlotsInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.calendars as cal_mod
    cal_mod.register(_FakeMCP())
    fn = _calls[5]

    await fn(CalendarFreeSlotsInput(
        calendar_id="cal1",
        start_date="1746835200000",
        end_date="1747008000000",
        timezone="Australia/Sydney",
    ))
    sent_url = str(route.calls[0].request.url)
    assert "timezone=Australia" in sent_url or "Australia" in sent_url


@respx.mock
@pytest.mark.asyncio
async def test_calendars_get_free_slots_markdown() -> None:
    """Free slots in markdown format renders as a code block (no custom renderer)."""
    slots_payload = {"2026-05-10": [{"startTime": "09:00", "endTime": "09:30"}]}
    respx.get(f"{BASE_URL}/calendars/cal2/free-slots").mock(
        return_value=Response(200, json=slots_payload)
    )

    from ghl_mcp.tools.calendars import CalendarFreeSlotsInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.calendars as cal_mod
    cal_mod.register(_FakeMCP())
    fn = _calls[5]

    result = await fn(CalendarFreeSlotsInput(
        calendar_id="cal2",
        start_date="1746835200000",
        end_date="1747008000000",
        response_format="markdown",
    ))
    # No custom renderer for free-slots — falls back to JSON-in-codeblock.
    assert "2026-05-10" in result
    assert "09:00" in result


@respx.mock
@pytest.mark.asyncio
async def test_calendars_get_free_slots_401_surfaces_clear_error() -> None:
    """A 401 on free-slots raises GHLAuthError with a useful message."""
    respx.get(f"{BASE_URL}/calendars/cal1/free-slots").mock(
        return_value=Response(401, json={"message": "Unauthorized"})
    )

    from ghl_mcp.tools.calendars import CalendarFreeSlotsInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.calendars as cal_mod
    cal_mod.register(_FakeMCP())
    fn = _calls[5]

    with pytest.raises(GHLAuthError) as excinfo:
        await fn(CalendarFreeSlotsInput(
            calendar_id="cal1",
            start_date="1746835200000",
            end_date="1747008000000",
        ))
    error_msg = str(excinfo.value).lower()
    assert "expire" in error_msg or "scope" in error_msg or "token" in error_msg


# ===========================================================================
# Cross-cutting: 401 hint quality
# ===========================================================================


@respx.mock
@pytest.mark.asyncio
async def test_401_hint_mentions_private_integration_token() -> None:
    """The GHLAuthError message mentions Private Integration Token specifically."""
    respx.get(f"{BASE_URL}/contacts/").mock(
        return_value=Response(401, json={"message": "invalid_token"})
    )

    from ghl_mcp.tools.contacts import ContactsListInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.contacts as contacts_mod
    contacts_mod.register(_FakeMCP())
    fn = _calls[0]

    with pytest.raises(GHLAuthError) as excinfo:
        await fn(ContactsListInput(location_id=LOCATION_ID))
    # The hint from errors.py references PITs explicitly.
    assert "token" in str(excinfo.value).lower() or "pit" in str(excinfo.value).lower()


@respx.mock
@pytest.mark.asyncio
async def test_contacts_list_request_carries_location_id() -> None:
    """The location_id is forwarded as a query param to the GHL contacts endpoint."""
    route = respx.get(f"{BASE_URL}/contacts/").mock(
        return_value=Response(200, json={"contacts": [], "total": 0})
    )

    from ghl_mcp.tools.contacts import ContactsListInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.contacts as contacts_mod
    contacts_mod.register(_FakeMCP())
    fn = _calls[0]

    await fn(ContactsListInput(location_id=LOCATION_ID, response_format="json"))
    sent_url = str(route.calls[0].request.url)
    assert f"locationId={LOCATION_ID}" in sent_url


@respx.mock
@pytest.mark.asyncio
async def test_opportunities_list_request_carries_location_id() -> None:
    """The location_id is forwarded as a query param to the opportunities search endpoint."""
    route = respx.get(f"{BASE_URL}/opportunities/search").mock(
        return_value=Response(200, json={"opportunities": [], "total": 0})
    )

    from ghl_mcp.tools.opportunities import OpportunitiesListInput

    _calls: list[Any] = []

    class _FakeMCP:
        def tool(self, **kwargs):
            def decorator(fn):
                _calls.append(fn)
                return fn
            return decorator

    import ghl_mcp.tools.opportunities as opps_mod
    opps_mod.register(_FakeMCP())
    fn = _calls[0]

    await fn(OpportunitiesListInput(location_id=LOCATION_ID, response_format="json"))
    sent_url = str(route.calls[0].request.url)
    assert f"location_id={LOCATION_ID}" in sent_url
