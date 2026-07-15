"""Unit tests for configuration and multi-client resolution.

Covers GHL_CLIENTS parsing, the resolve_client() precedence rules (explicit
location_id > GHL_DEFAULT_LOCATION_ID > sole configured client), and the
legacy GHL_API_KEY/GHL_LOCATION_ID single-client fallback. Also covers the
company-ID auto-detection used only for the startup pre-flight log line.

Run with: ``pytest tests/test_config.py -v``
"""

from __future__ import annotations

import logging

import pytest

import ghl_mcp.config as cfg
from ghl_mcp import __main__ as entry


@pytest.fixture(autouse=True)
def _clean_resolved_company_id():
    """Reset the module-level auto-detected ID before and after each test."""
    cfg._resolved_company_id = None
    yield
    cfg._resolved_company_id = None


def _settings(**overrides) -> cfg.Settings:
    base = dict(
        clients={},
        default_location_id=None,
        company_id=None,
        base_url="https://services.leadconnectorhq.com",
        api_version="2021-07-28",
        timeout=30.0,
        max_retries=3,
        log_level="INFO",
    )
    base.update(overrides)
    return cfg.Settings(**base)


def _account(location_id: str, label: str | None = None) -> cfg.ClientAccount:
    return cfg.ClientAccount(location_id=location_id, api_key=f"pit-{location_id}", label=label or location_id)


# ---------------------------------------------------------------------------
# GHL_CLIENTS parsing
# ---------------------------------------------------------------------------


def test_parse_clients_valid_json() -> None:
    raw = '{"loc-1": {"api_key": "pit-a", "label": "Client A"}}'
    clients = cfg._parse_clients(raw)
    assert clients["loc-1"].api_key == "pit-a"
    assert clients["loc-1"].label == "Client A"
    assert clients["loc-1"].location_id == "loc-1"


def test_parse_clients_defaults_label_to_location_id() -> None:
    raw = '{"loc-1": {"api_key": "pit-a"}}'
    clients = cfg._parse_clients(raw)
    assert clients["loc-1"].label == "loc-1"


def test_parse_clients_none_returns_empty() -> None:
    assert cfg._parse_clients(None) == {}
    assert cfg._parse_clients("") == {}


def test_parse_clients_invalid_json_raises() -> None:
    with pytest.raises(RuntimeError, match="not valid JSON"):
        cfg._parse_clients("{not json")


def test_parse_clients_non_object_raises() -> None:
    with pytest.raises(RuntimeError, match="JSON object"):
        cfg._parse_clients('["loc-1"]')


def test_parse_clients_missing_api_key_raises() -> None:
    with pytest.raises(RuntimeError, match="missing an api_key"):
        cfg._parse_clients('{"loc-1": {"label": "Client A"}}')


# ---------------------------------------------------------------------------
# resolve_client precedence
# ---------------------------------------------------------------------------


def test_resolve_client_no_clients_raises() -> None:
    s = _settings()
    with pytest.raises(RuntimeError, match="No GHL clients are configured"):
        s.resolve_client()


def test_resolve_client_explicit_location_id_wins() -> None:
    s = _settings(clients={"loc-1": _account("loc-1"), "loc-2": _account("loc-2")}, default_location_id="loc-1")
    assert s.resolve_client("loc-2").location_id == "loc-2"


def test_resolve_client_unknown_location_id_raises_with_known_list() -> None:
    s = _settings(clients={"loc-1": _account("loc-1", "Client A")})
    with pytest.raises(ValueError, match="Unknown location_id"):
        s.resolve_client("loc-nonexistent")


def test_resolve_client_falls_back_to_default() -> None:
    s = _settings(
        clients={"loc-1": _account("loc-1"), "loc-2": _account("loc-2")},
        default_location_id="loc-2",
    )
    assert s.resolve_client().location_id == "loc-2"


def test_resolve_client_default_pointing_at_unknown_client_raises() -> None:
    s = _settings(clients={"loc-1": _account("loc-1")}, default_location_id="loc-missing")
    with pytest.raises(RuntimeError, match="GHL_DEFAULT_LOCATION_ID"):
        s.resolve_client()


def test_resolve_client_sole_client_used_without_default() -> None:
    s = _settings(clients={"loc-1": _account("loc-1")})
    assert s.resolve_client().location_id == "loc-1"


def test_resolve_client_multiple_clients_no_location_no_default_raises() -> None:
    s = _settings(clients={"loc-1": _account("loc-1"), "loc-2": _account("loc-2")})
    with pytest.raises(ValueError, match="Multiple clients configured"):
        s.resolve_client()


# ---------------------------------------------------------------------------
# Legacy single-client fallback (GHL_API_KEY / GHL_LOCATION_ID)
# ---------------------------------------------------------------------------


def test_load_settings_legacy_env_vars(monkeypatch) -> None:
    monkeypatch.delenv("GHL_CLIENTS", raising=False)
    monkeypatch.setenv("GHL_API_KEY", "pit-legacy")
    monkeypatch.setenv("GHL_LOCATION_ID", "loc-legacy")
    s = cfg._load_settings()
    assert s.clients["loc-legacy"].api_key == "pit-legacy"
    assert s.resolve_client().location_id == "loc-legacy"


def test_load_settings_ghl_clients_takes_precedence_over_legacy(monkeypatch) -> None:
    monkeypatch.setenv("GHL_CLIENTS", '{"loc-new": {"api_key": "pit-new"}}')
    monkeypatch.setenv("GHL_API_KEY", "pit-legacy")
    monkeypatch.setenv("GHL_LOCATION_ID", "loc-legacy")
    s = cfg._load_settings()
    assert "loc-legacy" not in s.clients
    assert s.clients["loc-new"].api_key == "pit-new"


# ---------------------------------------------------------------------------
# require_company_id resolution order (unchanged behaviour, new Settings shape)
# ---------------------------------------------------------------------------


def test_explicit_override_wins() -> None:
    s = _settings(company_id="env-agency")
    cfg.set_resolved_company_id("detected-agency")
    assert s.require_company_id("explicit-agency") == "explicit-agency"


def test_env_value_beats_detected() -> None:
    s = _settings(company_id="env-agency")
    cfg.set_resolved_company_id("detected-agency")
    assert s.require_company_id() == "env-agency"


def test_falls_back_to_detected_when_env_unset() -> None:
    s = _settings(company_id=None)
    cfg.set_resolved_company_id("detected-agency")
    assert s.require_company_id() == "detected-agency"


def test_raises_when_nothing_available() -> None:
    s = _settings(company_id=None)
    with pytest.raises(ValueError, match="company ID"):
        s.require_company_id()


# ---------------------------------------------------------------------------
# set_resolved_company_id is a guarded setter
# ---------------------------------------------------------------------------


def test_setter_ignores_falsy_values() -> None:
    cfg.set_resolved_company_id("good")
    cfg.set_resolved_company_id(None)
    cfg.set_resolved_company_id("")
    assert cfg.get_resolved_company_id() == "good"


# ---------------------------------------------------------------------------
# _auto_detect_company_id body parsing
# ---------------------------------------------------------------------------


def test_auto_detect_from_nested_location(monkeypatch) -> None:
    monkeypatch.setattr(cfg, "settings", _settings(company_id=None))
    monkeypatch.setattr(entry, "settings", cfg.settings)
    body = b'{"location": {"id": "loc-test", "companyId": "agency-123"}}'
    entry._auto_detect_company_id(logging.getLogger("test"), body)
    assert cfg.get_resolved_company_id() == "agency-123"


def test_auto_detect_respects_explicit_env(monkeypatch) -> None:
    """A configured GHL_COMPANY_ID must not be overwritten by detection."""
    monkeypatch.setattr(cfg, "settings", _settings(company_id="pinned"))
    monkeypatch.setattr(entry, "settings", cfg.settings)
    body = b'{"location": {"companyId": "agency-123"}}'
    entry._auto_detect_company_id(logging.getLogger("test"), body)
    assert cfg.get_resolved_company_id() is None  # detection skipped
    assert cfg.settings.require_company_id() == "pinned"


def test_auto_detect_tolerates_bad_body(monkeypatch) -> None:
    monkeypatch.setattr(cfg, "settings", _settings(company_id=None))
    monkeypatch.setattr(entry, "settings", cfg.settings)
    entry._auto_detect_company_id(logging.getLogger("test"), b"not json")
    entry._auto_detect_company_id(logging.getLogger("test"), b"")
    entry._auto_detect_company_id(logging.getLogger("test"), b'{"location": {}}')
    assert cfg.get_resolved_company_id() is None
