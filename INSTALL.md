# GHL MCP — Install Guide

Connects Claude Desktop to your GoHighLevel account via 78 API tools.

---

## Mac

### Step 1 — Install prerequisites

You need Python 3.10+ and Git. Check what you have:

```bash
python3 --version
git --version
```

If either is missing:
- **Python:** `brew install python@3.12` (install [Homebrew](https://brew.sh) first if needed)
- **Git:** `xcode-select --install`

You also need [Claude Desktop](https://claude.ai/download) installed.

---

### Step 2 — Run the installer

Download `install_mac.sh` from the repo and save it to your Downloads folder, then open **Terminal** and run:

```bash
bash ~/Downloads/install_mac.sh
```

The script will:
- Clone the repo to `~/.claude/mcp-servers/gohighlevel/`
- Create a Python virtual environment
- Install all dependencies
- Run a smoke test (should report 78 tools)
- Print a JSON config snippet

---

### Step 3 — Get your GoHighLevel credentials

You need two values from GoHighLevel:

**1. Private Integration Token (`GHL_API_KEY`)**
1. Log in to GoHighLevel
2. Go to **Settings → Private Integrations**
3. Click **Create new Integration**, give it a name
4. Enable these scopes:
   - Contacts: `readonly` + `write`
   - Conversations: `readonly` + `write` + message `readonly` + message `write`
   - Calendars: `readonly` + `write` + events `readonly` + events `write`
   - Opportunities: `readonly` + `write`
   - Custom Fields: `readonly` + `write`
   - Locations: `readonly` + `write`
   - Workflows: `readonly`
   - Forms: `readonly`
   - Users: `readonly` + `write`
   - Webhooks: `readonly` + `write`
   - *(Agency only)* Snapshots: `readonly` + `write`
   - *(Agency only)* SaaS Locations: `read` + `write`
   - *(Agency only)* Companies: `readonly`
5. Save and copy the token — it starts with `pit-`

> **Agency owners:** tick the three *(Agency only)* scopes above. Without them, the agency tools (snapshots, sub-account management, companies) return **401 errors** even though everything else works — a 401 on those tools almost always means a missing agency scope, not an expired token.

> **Note:** Private Integration Tokens expire after 90 days of non-use. If tools stop working with 401 errors, come back here and regenerate the token, then update `GHL_API_KEY` in your Claude Desktop config.

**2. Location ID (`GHL_LOCATION_ID`)**
1. Go to **Settings → Business Profile**
2. Copy the Location ID shown on the page (or in the URL)

---

### Step 4 — Configure Claude Desktop

Open the Claude Desktop config file:

```bash
open -e ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

If the file doesn't exist, create it. Paste the JSON snippet printed by the installer, then replace the two placeholder values with your credentials:

```json
{
  "mcpServers": {
    "gohighlevel": {
      "command": "/Users/YOUR_USERNAME/.claude/mcp-servers/gohighlevel/venv/bin/python",
      "args": ["-m", "ghl_mcp"],
      "env": {
        "GHL_API_KEY": "pit-your-token-here",
        "GHL_LOCATION_ID": "your-location-id-here"
      }
    }
  }
}
```

> If you already have other MCP servers configured, add only the `gohighlevel` block inside your existing `mcpServers` object — don't replace the whole file.

---

### Step 5 — Restart Claude Desktop

Quit fully with **⌘Q** (just closing the window is not enough), then reopen.

---

### Step 6 — Verify

In a new Claude Desktop chat, type:

> What GoHighLevel tools do you have?

You should see ~78 tools listed. Then try a real query:

> List the first 5 contacts in my GHL account.

---

### Mac — Troubleshooting

| Problem | Fix |
|---|---|
| No GHL tools appear | Check logs at `~/Library/Logs/Claude/mcp-server-gohighlevel.log` |
| "Server failed to start" | Re-run installer, paste fresh JSON snippet into config |
| JSON error on startup | Validate your config at [jsonlint.com](https://jsonlint.com) |
| 401 errors | PIT token expired — regenerate at GHL → Settings → Private Integrations |
| 401 only on agency tools (snapshots/SaaS/companies), rest work | Token is missing the agency scopes — edit the integration and tick Snapshots, SaaS Locations and Companies, then regenerate |
| Sudden 401 errors on tools that were working | Private Integration Tokens auto-expire after 90 days of non-use — regenerate at GHL → Settings → Private Integrations and update `GHL_API_KEY` in your config |
| Tools show but return nothing | Wrong Location ID — get it from GHL → Settings → Business Profile |
| Claude Desktop not picking up changes | Must fully quit with ⌘Q, not just close the window |

---
---

## Windows

### Step 1 — Install prerequisites

You need Python 3.10+ and Git.

- **Python 3.10+:** Download from [python.org/downloads](https://www.python.org/downloads/)
  > During install, tick **"Add python.exe to PATH"** — this is essential.
- **Git:** Download from [git-scm.com/download/win](https://git-scm.com/download/win)

You also need [Claude Desktop](https://claude.ai/download) installed.

After installing, open a new **PowerShell** window and confirm:

```powershell
python --version
git --version
```

---

### Step 2 — Run the installer

Download `install_windows.ps1` from the repo and save it to your Downloads folder, then open **PowerShell** (search "PowerShell" in the Start menu) and run:

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\Downloads\install_windows.ps1"
```

The script will:
- Clone the repo to `%USERPROFILE%\.claude\mcp-servers\gohighlevel\`
- Create a Python virtual environment
- Install all dependencies
- Run a smoke test (should report 78 tools)
- Print a JSON config snippet

---

### Step 3 — Get your GoHighLevel credentials

You need two values from GoHighLevel:

**1. Private Integration Token (`GHL_API_KEY`)**
1. Log in to GoHighLevel
2. Go to **Settings → Private Integrations**
3. Click **Create new Integration**, give it a name
4. Enable these scopes:
   - Contacts: `readonly` + `write`
   - Conversations: `readonly` + `write` + message `readonly` + message `write`
   - Calendars: `readonly` + `write` + events `readonly` + events `write`
   - Opportunities: `readonly` + `write`
   - Custom Fields: `readonly` + `write`
   - Locations: `readonly` + `write`
   - Workflows: `readonly`
   - Forms: `readonly`
   - Users: `readonly` + `write`
   - Webhooks: `readonly` + `write`
   - *(Agency only)* Snapshots: `readonly` + `write`
   - *(Agency only)* SaaS Locations: `read` + `write`
   - *(Agency only)* Companies: `readonly`
5. Save and copy the token — it starts with `pit-`

> **Agency owners:** tick the three *(Agency only)* scopes above. Without them, the agency tools (snapshots, sub-account management, companies) return **401 errors** even though everything else works — a 401 on those tools almost always means a missing agency scope, not an expired token.

> **Note:** Private Integration Tokens expire after 90 days of non-use. If tools stop working with 401 errors, come back here and regenerate the token, then update `GHL_API_KEY` in your Claude Desktop config.

**2. Location ID (`GHL_LOCATION_ID`)**
1. Go to **Settings → Business Profile**
2. Copy the Location ID shown on the page (or in the URL)

---

### Step 4 — Configure Claude Desktop

Open the Claude Desktop config file in Notepad:

```powershell
notepad "$env:APPDATA\Claude\claude_desktop_config.json"
```

If the file doesn't exist, create it. Paste the JSON snippet printed by the installer, then replace the two placeholder values with your credentials:

```json
{
  "mcpServers": {
    "gohighlevel": {
      "command": "C:/Users/YOUR_USERNAME/.claude/mcp-servers/gohighlevel/venv/Scripts/python.exe",
      "args": ["-m", "ghl_mcp"],
      "env": {
        "GHL_API_KEY": "pit-your-token-here",
        "GHL_LOCATION_ID": "your-location-id-here"
      }
    }
  }
}
```

> If you already have other MCP servers configured, add only the `gohighlevel` block inside your existing `mcpServers` object — don't replace the whole file.

---

### Step 5 — Restart Claude Desktop

Right-click the Claude icon in the **system tray** (bottom-right) and click **Quit** — closing the window is not enough. Then reopen Claude Desktop.

---

### Step 6 — Verify

In a new Claude Desktop chat, type:

> What GoHighLevel tools do you have?

You should see ~78 tools listed. Then try a real query:

> List the first 5 contacts in my GHL account.

---

### Windows — Troubleshooting

| Problem | Fix |
|---|---|
| No GHL tools appear | Check logs at `%APPDATA%\Claude\logs\mcp-server-gohighlevel.log` |
| "Server failed to start" | Re-run installer, paste fresh JSON snippet into config |
| JSON error on startup | Validate your config at [jsonlint.com](https://jsonlint.com) |
| 401 errors | PIT token expired — regenerate at GHL → Settings → Private Integrations |
| 401 only on agency tools (snapshots/SaaS/companies), rest work | Token is missing the agency scopes — edit the integration and tick Snapshots, SaaS Locations and Companies, then regenerate |
| Sudden 401 errors on tools that were working | Private Integration Tokens auto-expire after 90 days of non-use — regenerate at GHL → Settings → Private Integrations and update `GHL_API_KEY` in your config |
| Tools show but return nothing | Wrong Location ID — get it from GHL → Settings → Business Profile |
| Claude Desktop not picking up changes | Must Quit from the system tray, not just close the window |
| `python` not found after install | Re-install Python and tick "Add python.exe to PATH" |
| PowerShell says "cannot be loaded" | Run with `-ExecutionPolicy Bypass` as shown above |

---
---

## Updating

Re-run the installer script at any time. It does a `git pull` on the existing install and reinstalls — your config stays the same. Restart Claude Desktop after.

---

## Agency / SaaS features

> **Good news for agency owners: there is nothing extra to configure.** The agency tools work with the same two values everyone uses (`GHL_API_KEY` and `GHL_LOCATION_ID`).

The following tool categories operate at the agency level:

| Tool category | What it does |
|---|---|
| **Snapshots** | Create, list, and apply account snapshots |
| **SaaS / sub-account management** | Create, update, enable/disable sub-accounts |
| **Companies** | Agency-level company record operations |
| **Funnels** | Funnel management across the agency |

These need your agency/company ID — but you don't have to hunt for it. On startup the server reads it automatically from your location record and enables the agency tools. As long as your token is valid **and has the agency scopes** (Snapshots, SaaS Locations, Companies — see Step 3), they just work.

### Pinning a specific agency (optional)

The only time you need to set `GHL_COMPANY_ID` yourself is if you want to **pin** a particular agency — for example, if your token can see more than one. In that case add it to the `env` block:

```json
"env": {
  "GHL_API_KEY": "pit-your-token-here",
  "GHL_LOCATION_ID": "your-location-id-here",
  "GHL_COMPANY_ID": "your-agency-id-here"
}
```

To find your agency ID, either look in GoHighLevel → Agency Settings, or start the server once and copy it from the log:

```
Agency/company ID auto-detected from your location: <your-agency-id>
```

### Not sure which location ID to use?

If you manage several sub-accounts and aren't sure which one to set as your default `GHL_LOCATION_ID`, the bundled helper lists every location your token can access:

```bash
GHL_API_KEY=pit-your-token GHL_LOCATION_ID=any-location-you-know \
  python scripts/discover_locations.py
```

It prints each sub-account's name and ID (read-only — it changes nothing), so you can pick the one you want as your default.
