#!/usr/bin/env python3
"""Generate docs/TOOLS.md from registered FastMCP tools.

Run: python -m scripts.gen_tools_doc
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Allow import from sibling package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Bypass settings validation for doc generation
os.environ.setdefault("GHL_API_KEY", "pit-doc-gen-dummy")
os.environ.setdefault("GHL_LOCATION_ID", "doc-gen-dummy")
os.environ.setdefault("GHL_COMPANY_ID", "doc-gen-dummy")

from ghl_mcp.server import mcp  # noqa: E402


async def main() -> None:
    tools = await mcp.list_tools()
    by_cat: dict[str, list] = {}
    for t in tools:
        parts = t.name.split("_", 2)
        cat = parts[1] if len(parts) >= 2 else "misc"
        by_cat.setdefault(cat, []).append(t)

    lines: list[str] = []
    lines.append("# GoHighLevel MCP — Tool Reference")
    lines.append("")
    lines.append(
        f"**Total tools:** {len(tools)} across {len(by_cat)} categories."
    )
    lines.append("")
    lines.append(
        "Auto-generated from FastMCP registration. "
        "Regenerate with `python -m scripts.gen_tools_doc`."
    )
    lines.append("")
    lines.append("## Index")
    lines.append("")
    for cat in sorted(by_cat):
        lines.append(f"- [{cat}](#{cat}) — {len(by_cat[cat])} tools")
    lines.append("")
    lines.append("---")
    lines.append("")

    for cat in sorted(by_cat):
        lines.append(f"## {cat}")
        lines.append("")
        for t in sorted(by_cat[cat], key=lambda x: x.name):
            ann = t.annotations or {}
            # FastMCP returns ToolAnnotations objects with attribute access
            def _flag(name: str) -> bool:
                return getattr(ann, name, None) is True if not isinstance(ann, dict) else bool(ann.get(name))

            ro = "🔒 read-only" if _flag("readOnlyHint") else "✏️ mutating"
            dest = " ⚠️ destructive" if _flag("destructiveHint") else ""
            idem = " ♻️ idempotent" if _flag("idempotentHint") else ""

            title = (
                getattr(ann, "title", None)
                if not isinstance(ann, dict)
                else ann.get("title")
            ) or "_(no title)_"

            lines.append(f"### `{t.name}`")
            lines.append("")
            lines.append(f"*{title}* · {ro}{dest}{idem}")
            lines.append("")
            desc_first_line = (t.description or "").strip().split("\n")[0]
            if desc_first_line:
                lines.append(desc_first_line)
                lines.append("")

    out_path = Path(__file__).resolve().parent.parent / "docs" / "TOOLS.md"
    out_path.write_text("\n".join(lines))
    print(f"Wrote {out_path}: {len(lines)} lines")


if __name__ == "__main__":
    asyncio.run(main())
