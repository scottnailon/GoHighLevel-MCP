# Architecture Notes

Design rationale for the v2 rewrite. Each section explains *why* a choice was made, not just what it is.

## Why FastMCP over the low-level `Server` class

The v1 used `mcp.server.Server` with manual `@app.list_tools()` and `@app.call_tool()` decorators. That pattern requires:

1. Defining each tool's schema as a `Tool(...)` object inside `list_tools()` (~580 lines in v1).
2. Implementing the actual handler inside a giant `if name == "...": elif name == "...":` chain in `call_tool()` (~340 lines in v1).
3. Manually parsing `arguments` dicts at the start of each handler.
4. Manually serializing return values to `TextContent`.

That's ~900 lines of boilerplate before the first line of useful logic.

**FastMCP** (the high-level Python SDK) eliminates all of that. Tools register via decorator on the implementation function itself:

```python
@mcp.tool(name="ghl_contacts_get", annotations={...})
async def ghl_contacts_get(params: ContactGetInput) -> str:
    ...
```

Schema is auto-generated from the Pydantic input model. Annotations are first-class. The dispatch table is built and maintained by the framework. The result: the same tool surface in roughly 30% of the code, with better validation, clearer error messages, and stronger type safety.

The MCP best-practices spec explicitly recommends FastMCP for new Python servers.

## Why Pydantic v2 for input validation

The v1 used `arguments.get("contact_id")` with manual checks like `if not contact_id: return error`. This is fragile:

- No type coercion (a numeric ID passed as `"42"` works in some places and breaks in others).
- No length / range / regex validation.
- Constraints (max 100 contacts per page, valid country codes, etc.) live in human-readable docstrings only — not enforced.
- Error messages are inconsistent across tools.

Pydantic v2 gives us:

- Automatic JSON Schema generation that the MCP client uses to constrain tool calls.
- Strict typing with helpful error messages when the model rejects input.
- Reusable mixins (`LocationScopedInput`, `PaginationInput`) so common parameter shapes are defined once.
- Forbidding extra fields (`extra="forbid"`) catches typos in tool calls early.

## Why a singleton client over per-call connections

The v1 created a fresh `httpx.AsyncClient` per request inside `ghl_request`. Each request paid the TCP+TLS handshake cost.

The v2 uses a process-wide singleton (`get_client()`) that:

- Opens a connection pool on first use and keeps it warm.
- Reuses HTTP/2 connections across many tool calls within a session.
- Cleans up on shutdown via `close_client()`.

For an agent doing 20+ tool calls in a single user turn, this is a meaningful latency win.

## Why header-based rate limiting

The v1 used a custom sliding-window counter (a `deque` of timestamps) to enforce 100 requests / 10 seconds locally. Problems:

- It assumed GHL's published limits, but the real limits depend on plan tier and resource. The local counter could reject requests GHL would have accepted, or vice versa.
- Multiple concurrent processes (separate MCP server instances) didn't coordinate.
- The library had no awareness of *daily* limits (200k / day per resource).

The v2 reads GHL's response headers (`X-RateLimit-Remaining`, `Retry-After`) directly:

- Always accurate — GHL is the authoritative source.
- Logs a warning when remaining drops below 25 and again at 10.
- Honors `Retry-After` for the exponential backoff on 429.
- No coordination needed between processes.

## Why typed exceptions over dict-with-error-key

The v1 returned `{"error": "...", "details": "..."}` for any failure. This worked but:

- Forced every tool to handle the dict-or-data union.
- Couldn't easily distinguish "permission denied" from "rate limit" from "validation failure" in calling code.
- Lost the HTTP status code unless explicitly logged.

The v2 raises typed exceptions:

- `GHLAuthError` (401/403) — includes a hint about token expiry and scopes.
- `GHLNotFoundError` (404) — the resource doesn't exist.
- `GHLValidationError` (400/422) — the request body or query is malformed.
- `GHLRateLimitError` (429) — includes a hint about burst vs daily limits.
- `GHLServerError` (5xx) — upstream issue, retry may help.
- `GHLTimeoutError` — request didn't complete in time.

Tools catch these to either retry or surface a useful message to the agent. The MCP framework converts uncaught exceptions to `isError: true` automatically.

## Why both Markdown and JSON response formats

The MCP best-practices spec asks tools to support both. They serve different consumers:

- **Markdown** is for the agent reading the result and deciding what to do next. Concise tables and human-readable timestamps minimize context window cost.
- **JSON** is for downstream programmatic processing — e.g., when an agent is building a CSV file or feeding the result to another tool.

The default is Markdown for context efficiency. Agents pass `response_format="json"` when they need the structured shape.

## Why modular tools/ package

The v1 was one 1,061-line file. The v2 splits into 13 modules in `ghl_mcp/tools/`. Why:

- Each module is focused on one resource type — easy to find and audit.
- New API endpoints can be added by editing one small file rather than navigating a giant if-chain.
- Tool modules can have private helpers without polluting a global namespace.
- `tests/test_imports.py` parameterizes over module names — adding a module = adding one line to the test list.
- Code review diffs are scoped to the relevant module.

Each module exposes a `register(mcp)` function. The top-level `tools/__init__.py` calls each in order. This is the cleanest way to keep the registration order explicit while letting modules be self-contained.

## Why `{service}_mcp` naming

Per MCP best practices: server name = `{service}_mcp` (snake_case), tool name = `{service}_{action}_{resource}` (snake_case with service prefix).

The v1's server name was `gohighlevel`, which:

- Doesn't follow the convention.
- Could conflict with other tools if multiple `gohighlevel*` servers run alongside each other.

`gohighlevel_mcp` is unambiguous and matches what the skill spec expects.

## Trade-offs explicitly NOT taken

For honesty, here's what we chose *not* to do:

- **Auto-pagination**: We don't transparently fetch all pages. Agents pass `skip` to fetch the next page. Reason: huge result sets would blow the context window. Better to surface pagination metadata and let the agent decide how many pages it actually needs.
- **OAuth 2.0 flow**: Only Private Integration Token auth is supported. OAuth is more secure for marketplace apps but adds significant complexity (refresh tokens, scope management, callback URLs) for marginal benefit in a single-tenant internal tool. If a marketplace app distribution is needed later, OAuth can be added without changing the tool surface.
- **Caching**: No tool result is cached. Reason: GHL data is mutable and stale results would be confusing. Modern GHL's response times are fast enough that caching isn't worth the complexity.
- **Bulk operations**: No `ghl_contacts_bulk_update` or similar. Reason: GHL's API doesn't natively support most bulk operations, so a "bulk" tool would internally loop through individual API calls — better to let the agent loop explicitly so it can handle partial failures and respect rate limits.
