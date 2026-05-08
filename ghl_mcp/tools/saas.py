"""SaaS-mode tools (5).

Operations specific to running GHL in SaaS mode — managing plans, enabling
SaaS on a sub-account, updating per-client pricing, and adjusting wallet
balances. Requires GHL SaaS Pro plan and the relevant scopes.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ghl_mcp.client import get_client
from ghl_mcp.config import settings
from ghl_mcp.formatters import format_response
from ghl_mcp.models import BaseToolInput, CompanyScopedInput, ResponseFormat


class SaasEnableInput(CompanyScopedInput):
    location_id: str = Field(..., min_length=1, description="Sub-account to enable SaaS mode on.")
    stripe_customer_id: str | None = Field(default=None, description="Pre-existing Stripe customer ID to attach.")
    plan_id: str | None = Field(default=None, description="Plan tier ID (founder/standard/etc).")
    trial_days: int | None = Field(default=None, ge=0, le=365)


class SaasUpdatePlanInput(CompanyScopedInput):
    location_id: str = Field(..., min_length=1)
    plan_id: str = Field(..., min_length=1, description="The new plan tier to move the sub-account to.")


class SaasDisableInput(CompanyScopedInput):
    location_id: str = Field(..., min_length=1)


class SaasGetSubInput(BaseToolInput):
    location_id: str = Field(..., min_length=1)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class SaasWalletAdjustInput(BaseToolInput):
    location_id: str = Field(..., min_length=1, description="Sub-account whose wallet to adjust.")
    amount: float = Field(..., description="Amount in account currency. Positive to credit, negative to debit.")
    description: str = Field(..., min_length=1, max_length=500, description="Reason for adjustment, shown in audit log.")


def register(mcp) -> None:  # noqa: ANN001
    @mcp.tool(
        name="ghl_saas_enable",
        annotations={"title": "Enable SaaS on sub-account", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def ghl_saas_enable(params: SaasEnableInput) -> str:
        """Enable SaaS billing on a sub-account, optionally attaching a Stripe customer and selecting a plan.

        After this succeeds, GHL begins billing the sub-account according to
        the plan's monthly/annual rate plus configured usage markups.
        """
        client = await get_client()
        company_id = settings.require_company_id(params.company_id)
        body: dict[str, Any] = {
            "companyId": company_id,
            "locationId": params.location_id,
        }
        if params.stripe_customer_id:
            body["stripeCustomerId"] = params.stripe_customer_id
        if params.plan_id:
            body["planId"] = params.plan_id
        if params.trial_days is not None:
            body["trialDays"] = params.trial_days
        result = await client.post("/saas-api/public-api/enable-saas", json=body)
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(
        name="ghl_saas_disable",
        annotations={"title": "Disable SaaS on sub-account", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": True},
    )
    async def ghl_saas_disable(params: SaasDisableInput) -> str:
        """Disable SaaS billing on a sub-account, ending the subscription. The sub-account itself is not deleted."""
        client = await get_client()
        company_id = settings.require_company_id(params.company_id)
        result = await client.post("/saas-api/public-api/disable-saas", json={
            "companyId": company_id,
            "locationId": params.location_id,
        })
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(
        name="ghl_saas_update_plan",
        annotations={"title": "Change sub-account plan tier", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def ghl_saas_update_plan(params: SaasUpdatePlanInput) -> str:
        """Move a sub-account to a different plan tier. Useful for upgrading or downgrading clients."""
        client = await get_client()
        company_id = settings.require_company_id(params.company_id)
        result = await client.post("/saas-api/public-api/update-saas-subscription", json={
            "companyId": company_id,
            "locationId": params.location_id,
            "planId": params.plan_id,
        })
        return format_response(result, ResponseFormat.JSON)

    @mcp.tool(
        name="ghl_saas_get_subscription",
        annotations={"title": "Get sub-account SaaS subscription", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def ghl_saas_get_subscription(params: SaasGetSubInput) -> str:
        """Get the current SaaS subscription details for a sub-account: plan, status, next billing date, wallet balance."""
        client = await get_client()
        result = await client.get(f"/saas-api/public-api/saas-subscription/{params.location_id}")
        return format_response(result, params.response_format)

    @mcp.tool(
        name="ghl_saas_wallet_adjust",
        annotations={"title": "Adjust sub-account wallet balance", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def ghl_saas_wallet_adjust(params: SaasWalletAdjustInput) -> str:
        """Manually credit or debit a sub-account's GHL wallet (used for SMS/email/AI usage).

        Positive ``amount`` credits the wallet (e.g. founder welcome credit).
        Negative ``amount`` debits it (e.g. correction). Always provide a
        descriptive ``description`` — it appears in the audit log.
        """
        client = await get_client()
        result = await client.post(f"/saas-api/public-api/wallet/{params.location_id}/adjust", json={
            "amount": params.amount,
            "description": params.description,
        })
        return format_response(result, ResponseFormat.JSON)
