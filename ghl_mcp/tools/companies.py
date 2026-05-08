"""Company / Agency tools (1).

The company resource represents your top-level GHL agency account. Useful for
verifying agency context, retrieving agency-level branding, and confirming
which sub-accounts are accessible.
"""

from __future__ import annotations

from typing import Any

from ghl_mcp.client import get_client
from ghl_mcp.config import settings
from ghl_mcp.formatters import format_response
from ghl_mcp.models import CompanyScopedInput


class CompanyGetInput(CompanyScopedInput):
    pass


def _render_company(payload: dict[str, Any]) -> str:
    company = payload.get("company", payload)
    lines = [
        f"### {company.get('name', '?')} (`{company.get('id', '?')}`)",
        "",
        f"- **Email:** {company.get('email', '_unset_')}",
        f"- **Phone:** {company.get('phone', '_unset_')}",
        f"- **Website:** {company.get('website', '_unset_')}",
        f"- **Country:** {company.get('country', '_unset_')}",
        f"- **Timezone:** {company.get('timezone', '_unset_')}",
        f"- **Created:** {company.get('createdAt', '_unknown_')}",
    ]
    return "\n".join(lines)


def register(mcp) -> None:  # noqa: ANN001
    @mcp.tool(name="ghl_companies_get", annotations={"title": "Get agency/company details", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    async def ghl_companies_get(params: CompanyGetInput) -> str:
        """Get details about your GHL agency/company.

        Use this to verify which agency context the configured token operates
        in, retrieve agency-level metadata, or fetch the agency's branding
        and contact info.
        """
        client = await get_client()
        company_id = settings.require_company_id(params.company_id)
        result = await client.get(f"/companies/{company_id}")
        return format_response(result, params.response_format, markdown_renderer=_render_company)
