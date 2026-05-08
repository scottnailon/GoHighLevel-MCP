# GoHighLevel MCP Server

A production-grade [Model Context Protocol](https://modelcontextprotocol.io) server providing comprehensive, well-typed access to the [GoHighLevel](https://www.gohighlevel.com) CRM API for Claude Desktop and other MCP clients.

**78 tools across 18 resource categories.** Built for white-label SaaS, agency operations, and automation workflows.

---

## Installation

See [INSTALL.md](INSTALL.md) for the full Mac and Windows install guides.

### Quick start (server / developer)

```bash
git clone https://github.com/scottnailon/GoHighLevel-MCP.git
cd GoHighLevel-MCP
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -e .
cp .env.example .env
# Edit .env — add GHL_API_KEY, GHL_LOCATION_ID, optionally GHL_COMPANY_ID
```

---

## Configuration

All configuration is via environment variables. See `.env.example` for the full list with comments.

**Required:**
- `GHL_API_KEY` — your Private Integration Token (PIT). Generate at GHL → Settings → Private Integrations. Starts with `pit-`. **Expires after 90 days of non-use.**
- `GHL_LOCATION_ID` — default sub-account ID. Most tools accept a per-call override.

**Optional:**
- `GHL_COMPANY_ID` — required for agency-scoped tools: snapshots, SaaS management, sub-account CRUD, companies.
- `GHL_BASE_URL` — defaults to `https://services.leadconnectorhq.com`.
- `GHL_API_VERSION` — defaults to `2021-07-28`.
- `GHL_TIMEOUT` — request timeout in seconds, default 30.
- `GHL_MAX_RETRIES` — retries on 429/5xx, default 3.
- `GHL_LOG_LEVEL` — `DEBUG`, `INFO` (default), `WARNING`, `ERROR`.

### Required PIT scopes

```
contacts.readonly, contacts.write
conversations.readonly, conversations.write
conversations/message.readonly, conversations/message.write
calendars.readonly, calendars.write
calendars/events.readonly, calendars/events.write
opportunities.readonly, opportunities.write
custom-fields.readonly, custom-fields.write
locations.readonly, locations.write
saas/locations.read, saas/location.write
snapshots.readonly, snapshots.write
workflows.readonly
forms.readonly
users.readonly, users.write
webhooks.readonly, webhooks.write
```

---

## Running

```bash
python -m ghl_mcp
# or
ghl-mcp
```

### Claude Desktop config

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (Mac) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "gohighlevel": {
      "command": "/path/to/venv/bin/python",
      "args": ["-m", "ghl_mcp"],
      "env": {
        "GHL_API_KEY": "pit-your-token-here",
        "GHL_LOCATION_ID": "your-location-id",
        "GHL_COMPANY_ID": "your-agency-id"
      }
    }
  }
}
```

The install scripts in [INSTALL.md](INSTALL.md) print the exact JSON snippet with the correct Python path for your machine.

---

## Tool reference

78 tools across 18 modules. See [docs/TOOLS.md](docs/TOOLS.md) for the full list with parameters.

### Core CRM

| Prefix | Count | What it covers |
|---|---|---|
| `ghl_contacts_*` | 12 | Full contact lifecycle, tags, notes, tasks |
| `ghl_conversations_*` | 4 | List, get, create, search |
| `ghl_messages_*` | 4 | Send SMS, email, WhatsApp; list messages |
| `ghl_calendars_*` | 6 | Full CRUD + free-slot lookup |
| `ghl_appointments_*` | 4 | Book, list, get, update/cancel |
| `ghl_pipelines_*` | 5 | Full CRUD |
| `ghl_opportunities_*` | 8 | Full CRUD + stage and status transitions |
| `ghl_custom_fields_*` | 5 | Full CRUD for contact and opportunity fields |
| `ghl_tags_*` | 1 | List (tags managed via contact endpoints) |
| `ghl_users_*` | 4 | List, get, create, update |
| `ghl_workflows_*` | 2 | List, enrol contact |
| `ghl_forms_*` | 2 | List, get submissions |
| `ghl_funnels_*` | 2 | List, get pages |

### Agency / SaaS *(requires `GHL_COMPANY_ID`)*

| Prefix | Count | What it covers |
|---|---|---|
| `ghl_locations_*` | 5 | Sub-account CRUD |
| `ghl_snapshots_*` | 4 | List, get, import, share link |
| `ghl_saas_*` | 5 | Enable, disable, update plan, get subscription, wallet adjust |
| `ghl_webhooks_*` | 4 | Full CRUD |
| `ghl_companies_*` | 1 | Get agency details |

---

## Startup behaviour

On first run the server:

1. Checks that `GHL_API_KEY` and `GHL_LOCATION_ID` are set — logs step-by-step setup instructions if not.
2. Makes a live API call to verify the PIT is valid — logs a clear remediation banner if the token is expired (401) or missing scopes (403).
3. Logs an info hint if `GHL_COMPANY_ID` is unset (agency tools will be unavailable).

All checks log to **stderr only** — stdout carries the MCP JSON-RPC stream.

---

## Development

```bash
pip install -e ".[dev]"

# Run tests (64 total)
pytest

# Lint
ruff check ghl_mcp/

# Regenerate tool reference doc
python -m scripts.gen_tools_doc
```

### Project layout

```
ghl_mcp/
├── __init__.py          package metadata
├── __main__.py          CLI entrypoint + startup checks
├── config.py            environment-driven settings
├── errors.py            typed exception hierarchy
├── client.py            async httpx client, retry, rate-limit handling
├── models.py            shared Pydantic input models
├── pagination.py        pagination helpers + metadata
├── formatters.py        Markdown + JSON output rendering
├── server.py            FastMCP server + tool registration
└── tools/               18 modules, one per resource category
tests/
├── test_client.py       HTTP client unit tests (8)
├── test_imports.py      import + smoke tests (30)
└── test_tools.py        integration tests with mocked HTTP (26)
docs/
├── TOOLS.md             auto-generated tool reference
├── ARCHITECTURE.md      design rationale
└── MIGRATION.md         migration guide
```

### Adding a new tool

1. Pick or create a module in `ghl_mcp/tools/`.
2. Define a Pydantic input model inheriting `BaseToolInput`, `LocationScopedInput`, etc.
3. Add an `@mcp.tool` decorated function inside the module's `register(mcp)` call.
4. Make HTTP calls via `await get_client()`.
5. Register the module in `ghl_mcp/tools/__init__.py` if it's new.
6. Add an import to `tests/test_imports.py`.

---

## Architecture notes

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the rationale behind FastMCP, singleton client, header-based rate limiting, typed exceptions, dual response formats, and the modular tools package.

---

## License

MIT
