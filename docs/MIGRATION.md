# Migrating from v1 (`server.py`) to v2 (`ghl_mcp/`)

This guide walks through replacing the old single-file `server.py` with the new modular `ghl_mcp` package.

## TL;DR

1. Rename old file: `mv server.py server_v1.py.bak`
2. Install v2: `pip install -e .` (uses `pyproject.toml`)
3. Update `.mcp.json` / Claude Code config to call `python -m ghl_mcp` instead of `python server.py`
4. Regenerate Private Integration Token if expired (most users)
5. Test: `python -m ghl_mcp` — should start without errors

The old `server.py` continues to work until you cut over. There's no forced migration.

---

## What changed at the protocol level

### Server name

- **v1:** `gohighlevel`
- **v2:** `gohighlevel_mcp`

If your MCP client config references the server name, update accordingly.

### Tool names

Most tool names are unchanged. The few normalizations:

| v1 | v2 | Reason |
|---|---|---|
| `ghl_get_account_info` | `ghl_companies_get` | Match `{resource}_{action}` pattern |
| _(no equivalent)_ | `ghl_custom_fields_create` / `_update` / `_delete` | Was missing in v1 |
| _(no equivalent)_ | `ghl_pipelines_create` / `_update` / `_delete` | Was missing in v1 |
| _(no equivalent)_ | `ghl_snapshots_*` (4 tools) | Was missing in v1 |
| _(no equivalent)_ | `ghl_locations_create` / `_update` / `_delete` | Was missing in v1 |
| _(no equivalent)_ | `ghl_saas_*` (5 tools) | Was missing in v1 |
| _(no equivalent)_ | `ghl_webhooks_*` (4 tools) | Was missing in v1 |
| _(no equivalent)_ | `ghl_funnels_*` (2 tools) | Was missing in v1 |

### Response shape

**v1:** list endpoints returned the raw GHL response, e.g.:
```json
{"contacts": [...], "meta": {...}}
```

**v2:** list endpoints wrap with standardized pagination metadata:
```json
{
  "contacts": [...],
  "count": 20,
  "skip": 0,
  "limit": 20,
  "total": 137,
  "has_more": true,
  "next_skip": 20
}
```

**v2 also defaults to Markdown output.** Pass `response_format="json"` to any list/get tool to get the legacy structured shape.

### Error responses

**v1:** errors returned as dicts: `{"error": "...", "details": "..."}`

**v2:** errors raise typed exceptions caught by the MCP framework, returning `isError: true` per the protocol. Agents see clear, actionable error text.

### Pagination parameters

- **v1:** `limit` and `skip` were positional in the dict, varying by tool.
- **v2:** Always `limit` (1-100, default 20) and `skip` (>=0, default 0). Validated by Pydantic.

---

## Steps

### 1. Back up the old server

```bash
cp server.py server_v1.py.bak
```

### 2. Pull the v2 code

```bash
git pull origin main   # if v2 has been merged
# or work in a branch:
git checkout v2-rewrite
```

### 3. Install dependencies

The v1 used `requirements.txt`. v2 uses `pyproject.toml` (with `requirements.txt` mirrored for compatibility).

```bash
source venv/bin/activate
pip install -e .
# or for development tooling
pip install -e ".[dev]"
```

### 4. Verify your `.env`

The v2 uses the same env-var names as v1, plus a few new optional ones:

```bash
# Same as v1
GHL_API_KEY=pit-...
GHL_LOCATION_ID=...
GHL_BASE_URL=https://services.leadconnectorhq.com   # optional

# New in v2
GHL_COMPANY_ID=...                # optional; auto-detected at startup for agency tools
GHL_API_VERSION=2021-07-28         # was hardcoded in v1
GHL_TIMEOUT=30                     # configurable now
GHL_MAX_RETRIES=3                  # configurable now
GHL_LOG_LEVEL=INFO                 # new
```

### 5. Update your MCP client config

**Old (`.mcp.json` or Claude Desktop):**
```json
{
  "mcpServers": {
    "gohighlevel": {
      "command": "/path/to/venv/bin/python",
      "args": ["/path/to/GoHighLevel-MCP/server.py"]
    }
  }
}
```

**New:**
```json
{
  "mcpServers": {
    "gohighlevel": {
      "command": "/path/to/venv/bin/python",
      "args": ["-m", "ghl_mcp"],
      "cwd": "/path/to/GoHighLevel-MCP"
    }
  }
}
```

The key change: `args` becomes `["-m", "ghl_mcp"]` instead of `["server.py"]`. The `cwd` is needed so the package can find `.env`.

### 6. Smoke test

```bash
python -m ghl_mcp
# Should print "Starting GoHighLevel MCP server v2.0.0 (location_id=...)"
# and then wait silently on stdin for MCP protocol messages.
# Ctrl-C to exit.
```

If you see `RuntimeError: GHL_API_KEY is not configured`, you missed step 4.

### 7. Run the test suite (optional but recommended)

```bash
pip install -e ".[dev]"
pytest
```

You should see the imports test pass for all 18 tool modules and the client tests pass against mocked responses.

### 8. Test against live API

Start the server and watch stderr for the startup pre-flight output:

```bash
python -m ghl_mcp
```

If you see a `TOKEN EXPIRED OR INVALID` banner, your PIT has expired. Regenerate at GHL → Settings → Private Integrations and update `GHL_API_KEY` in your config.

### 9. Restart Claude

Restart Claude Code or Claude Desktop to pick up the new server. You should see 78 tools instead of v1's 46.

---

## Rollback

If anything breaks, the original `server.py` is unchanged. Revert your MCP client config back to:

```json
"args": ["server.py"]
```

…and you're back on v1.

---

## What happens to v1

The plan: leave `server.py` in the repo for one release, marked deprecated. Remove in v2.1 once we've confirmed v2 is stable in production usage. No date pressure.
