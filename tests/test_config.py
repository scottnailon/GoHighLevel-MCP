"""Unit tests for configuration and company-ID resolution.

Covers the agency-owner ergonomics added so that GHL_COMPANY_ID does not have
to be set by hand: the company ID is auto-detected from the location record at
startup, and require_company_id() falls back to that detected value.

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


# ---------------------------------------------------------------------------
# require_company_id resolution order
# ---------------------------------------------------------------------------


def _settings(**overrides) -> cfg.Settings:
    base = dict(
        api_key="pit-test",
        location_id="loc-test",
        company_id=None,
        base_url="https://services.leadconnectorhq.com",
        api_version="2021-07-28",
        timeout=30.0,
        max_retries=3,
        log_level="INFO",
    )
    base.update(overrides)
    return cfg.Settings(**base)


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
    with pytest.raises(ValueError, match="agency/company ID"):
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
