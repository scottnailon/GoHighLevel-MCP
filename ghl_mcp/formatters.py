"""Render tool output as JSON or Markdown."""

from __future__ import annotations

import json
from typing import Any

from ghl_mcp.models import ResponseFormat


# ---------------------------------------------------------------------------
# Formatting utilities
# ---------------------------------------------------------------------------


def fmt_currency(value: Any) -> str:
    """Format a numeric value as currency for display.

    GHL stores monetary values as plain numbers (dollars, not cents).
    We display with a dollar sign and comma-thousands separator.
    If the value is falsy/None, return an empty string.
    """
    if value is None or value == "" or value == 0:
        return ""
    try:
        fval = float(value)
    except (TypeError, ValueError):
        return str(value)
    # Format with 2 decimal places, then strip .00 for clean integers.
    formatted = f"${fval:,.2f}"
    if formatted.endswith(".00"):
        formatted = formatted[:-3]
    return formatted


def fmt_date(dt_str: str | None) -> str:
    """Strip the time component from an ISO 8601 datetime string.

    Returns just the YYYY-MM-DD part, or the original string if it cannot
    be parsed, or an empty string if ``dt_str`` is falsy.
    """
    if not dt_str:
        return ""
    # ISO strings look like "2026-01-15T10:00:00Z" or "2026-01-15T10:00:00.000Z"
    return str(dt_str)[:10]


def fmt_custom_fields_summary(custom_fields: list[dict[str, Any]] | None, max_fields: int = 3, max_chars: int = 40) -> str:
    """Render a compact one-line summary of custom fields for list views.

    Returns an empty string if there are no custom fields with values.
    """
    if not custom_fields:
        return ""
    pairs: list[str] = []
    for cf in custom_fields[:max_fields]:
        key = cf.get("fieldKey") or cf.get("id") or cf.get("name") or "?"
        val = cf.get("value")
        if val is None:
            continue
        val_str = str(val)
        if len(val_str) > max_chars:
            val_str = val_str[:max_chars - 1] + "…"
        pairs.append(f"{key}={val_str}")
    return ", ".join(pairs)


def format_response(
    data: Any,
    response_format: ResponseFormat | str,
    *,
    markdown_renderer: callable | None = None,
) -> str:
    """Render ``data`` using the requested format.

    For ``ResponseFormat.JSON``: pretty-printed JSON.

    For ``ResponseFormat.MARKDOWN``: if a ``markdown_renderer`` callable was
    provided, use it; otherwise fall back to JSON. Tool modules should pass
    a renderer for the resource type they handle.
    """
    fmt = response_format.value if isinstance(response_format, ResponseFormat) else response_format
    if fmt == "markdown":
        if markdown_renderer is not None:
            return markdown_renderer(data)
        # No custom renderer — fall back to JSON-in-codeblock for clarity.
        return f"```json\n{json.dumps(data, indent=2, default=str)}\n```"
    return json.dumps(data, indent=2, default=str)


# ---------------------------------------------------------------------------
# Common Markdown helpers
# ---------------------------------------------------------------------------


def md_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    """Render a list of dicts as a Markdown table.

    ``columns`` is a list of ``(field_key, header_label)`` tuples in display
    order. Missing keys render as empty strings. Pipe characters in cell values
    are escaped.
    """
    if not rows:
        return "_No results._"

    headers = [label for _, label in columns]
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        cells: list[str] = []
        for key, _ in columns:
            value = row.get(key, "")
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            elif value is None:
                value = ""
            cells.append(str(value).replace("|", r"\|").replace("\n", " "))
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


def md_section(title: str, body: str) -> str:
    """Wrap a body string under a Markdown header."""
    return f"### {title}\n\n{body}"


def md_pagination_footer(
    *,
    count: int,
    total: int | None,
    skip: int,
    limit: int,
    has_more: bool,
    next_skip: int | None,
    pagination_note: str | None = None,
) -> str:
    """Render the standard pagination footer in Markdown."""
    if total is not None:
        line = f"_Showing {skip + 1}–{skip + count} of {total} total._"
    else:
        line = f"_Showing {count} results starting at offset {skip}._"
    if has_more and next_skip is not None:
        line += f" Use `skip={next_skip}` to fetch the next page."
    if pagination_note:
        line += f" _(Note: {pagination_note}.)_"
    return line
