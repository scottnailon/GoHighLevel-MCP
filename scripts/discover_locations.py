#!/usr/bin/env python3
"""Discover which GHL locations a Private Integration Token can access.

Usage (token never needs to be pasted into a chat):

    GHL_API_KEY=pit-your-token venv/bin/python scripts/discover_locations.py

It will:
  1. Read the company/agency ID the token belongs to.
  2. List the sub-accounts (locations) under that agency.
  3. Print each location's name + ID so you can pick the right GHL_LOCATION_ID.

Read-only. Makes no changes.
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
import json

BASE = os.getenv("GHL_BASE_URL", "https://services.leadconnectorhq.com").rstrip("/")
VERSION = os.getenv("GHL_API_VERSION", "2021-07-28")
UA = "ghl-mcp/2.0.0"


def _get(path: str, params: dict | None = None) -> tuple[int, dict]:
    url = f"{BASE}{path}"
    if params:
        from urllib.parse import urlencode

        url += "?" + urlencode({k: v for k, v in params.items() if v})
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {os.environ['GHL_API_KEY']}",
            "Version": VERSION,
            "Accept": "application/json",
            "User-Agent": UA,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode("utf-8", "replace")[:300]}


def main() -> int:
    if not os.getenv("GHL_API_KEY"):
        print("Set GHL_API_KEY first, e.g.:")
        print("  GHL_API_KEY=pit-... venv/bin/python scripts/discover_locations.py")
        return 2

    # If a location is configured, resolve its company first (works for both
    # agency and sub-account tokens).
    company_id = os.getenv("GHL_COMPANY_ID")
    loc = os.getenv("GHL_LOCATION_ID")
    if loc and not company_id:
        status, body = _get(f"/locations/{loc}")
        if status == 200:
            location = body.get("location", body)
            company_id = location.get("companyId")
            print(f"Resolved agency/company ID from GHL_LOCATION_ID={loc}: {company_id}\n")

    if not company_id:
        print("No GHL_COMPANY_ID and could not resolve one from GHL_LOCATION_ID.")
        print("Pass one explicitly: GHL_COMPANY_ID=... GHL_API_KEY=... ... discover_locations.py")
        # Still try the search below in case the token is agency-scoped.

    # List sub-accounts under the agency. This endpoint needs an agency token.
    status, body = _get("/locations/search", {"companyId": company_id, "limit": "100"})
    if status != 200:
        print(f"GET /locations/search -> HTTP {status}")
        print(f"  {body.get('error', body)}")
        print("\nIf this is 401/403, the token likely lacks agency scopes "
              "(needs locations.readonly + agency access).")
        return 1

    locations = body.get("locations", body if isinstance(body, list) else [])
    if not locations:
        print("No locations returned. The token may only see a single sub-account.")
        return 0

    print(f"{len(locations)} location(s) accessible by this token:\n")
    print(f"{'NAME':<40}  LOCATION ID")
    print(f"{'-'*40}  {'-'*24}")
    for l in locations:
        print(f"{(l.get('name') or '?')[:40]:<40}  {l.get('id') or l.get('_id') or '?'}")
    print("\nPick the LOCATION ID you want as your default GHL_LOCATION_ID.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
