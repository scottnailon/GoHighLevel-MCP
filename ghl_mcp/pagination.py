"""Shared pagination utilities."""

from __future__ import annotations

from typing import Any


def build_pagination_response(
    items: list[Any],
    *,
    total: int | None,
    limit: int,
    skip: int,
    items_key: str = "items",
) -> dict[str, Any]:
    """Wrap a list of items with standard pagination metadata.

    The shape matches the MCP best-practices spec::

        {
            "<items_key>": [...],
            "count": 12,
            "skip": 0,
            "limit": 20,
            "total": 134,            # may be null if API doesn't report it
            "has_more": true,
            "next_skip": 20,         # null when has_more is false
            "pagination_note": "..."  # present only when total is unknown and
                                      # has_more is True (heuristic estimate)
        }

    GHL inconsistently reports totals — sometimes via ``meta.total``, sometimes
    in a top-level ``total``, sometimes not at all. Pass ``total=None`` when
    the API didn't tell us; ``has_more`` is then inferred from page-fullness
    (count >= limit), which is a heuristic that over-reports on a perfectly
    full last page. When that heuristic fires, ``pagination_note`` is added so
    the agent knows the result is an estimate.
    """
    count = len(items)
    pagination_note: str | None = None

    if total is not None:
        # Exact: we know the full count, so this is always correct.
        has_more = (skip + count) < total
    else:
        # Heuristic: if we got a full page there *might* be more results.
        # This returns True incorrectly when the last page is exactly full.
        has_more = count >= limit
        if has_more:
            pagination_note = (
                "total unknown — there may or may not be more results"
            )

    next_skip = (skip + count) if has_more else None

    result: dict[str, Any] = {
        items_key: items,
        "count": count,
        "skip": skip,
        "limit": limit,
        "total": total,
        "has_more": has_more,
        "next_skip": next_skip,
    }
    if pagination_note is not None:
        result["pagination_note"] = pagination_note
    return result


def extract_total(payload: dict[str, Any], *candidate_keys: str) -> int | None:
    """Try multiple known shapes for "total" in a GHL response."""
    if "meta" in payload and isinstance(payload["meta"], dict):
        for key in ("total", "totalCount", "count"):
            if key in payload["meta"]:
                value = payload["meta"][key]
                if isinstance(value, int):
                    return value
    for key in candidate_keys:
        if key in payload and isinstance(payload[key], int):
            return payload[key]
    return None
