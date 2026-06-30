# GHL MCP v2 — Windows install script for Claude Desktop
# Clones the repo and installs to %USERPROFILE%\.claude\mcp-servers\gohighlevel\
#
# Run with:
#   powershell -ExecutionPolicy Bypass -File install_windows.ps1
# Or right-click the file and choose "Run with PowerShell"
#
# To switch to GitHub after migration, update $RepoUrl below.

$ErrorActionPreference = "Stop"

$RepoUrl   = "https://github.com/scottnailon/GoHighLevel-MCP.git"
$InstallDir = Join-Path $HOME ".claude\mcp-servers\gohighlevel"

Write-Host "=== GHL MCP v2 installer (Windows) ===" -ForegroundColor Cyan
Write-Host ""

# 1. Find Python 3.10+
$PyExe = $null
foreach ($candidate in @("py", "python", "python3")) {
    try {
        $ver = & $candidate --version 2>&1
        if ($LASTEXITCODE -eq 0 -and $ver -match "Python 3\.(\d+)") {
            $minor = [int]$Matches[1]
            if ($minor -ge 10) {
                $PyExe = $candidate
                Write-Host "Python: $ver"
                break
            }
        }
    } catch { continue }
}
if (-not $PyExe) {
    Write-Host "ERROR: Python 3.10+ not found." -ForegroundColor Red
    Write-Host "Install from https://www.python.org/downloads/ — tick 'Add python.exe to PATH'." -ForegroundColor Red
    exit 1
}

# 2. Check git
try {
    $gitVer = & git --version 2>&1
    Write-Host "Git: $gitVer"
} catch {
    Write-Host "ERROR: git not found." -ForegroundColor Red
    Write-Host "Install Git for Windows from https://git-scm.com/download/win" -ForegroundColor Red
    exit 1
}

# 3. Clone or update
Write-Host ""
if (Test-Path (Join-Path $InstallDir ".git")) {
    Write-Host "Existing install found — pulling latest..."
    & git -C $InstallDir pull --ff-only
    if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: git pull failed" -ForegroundColor Red; exit 1 }
} else {
    Write-Host "Cloning from $RepoUrl ..."
    New-Item -ItemType Directory -Force -Path (Split-Path $InstallDir) | Out-Null
    & git clone $RepoUrl $InstallDir
    if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: git clone failed" -ForegroundColor Red; exit 1 }
}

# 4. Venv + install
Write-Host ""
Write-Host "Setting up venv..."
Push-Location $InstallDir
try {
    & $PyExe -m venv venv
    if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: venv creation failed" -ForegroundColor Red; exit 1 }

    $VenvPython = Join-Path $InstallDir "venv\Scripts\python.exe"
    Write-Host "Installing dependencies..."
    & $VenvPython -m pip install -e . --quiet --upgrade-strategy eager
    if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: pip install failed" -ForegroundColor Red; exit 1 }
} finally {
    Pop-Location
}

# 5. Smoke test
Write-Host ""
Write-Host "=== Smoke test ===" -ForegroundColor Cyan
$VenvPython = Join-Path $InstallDir "venv\Scripts\python.exe"
$env:GHL_API_KEY = "test"
$env:GHL_LOCATION_ID = "test"
$ToolCount = & $VenvPython -c @"
import asyncio
from ghl_mcp.server import mcp
async def c():
    t = await mcp.list_tools()
    print(len(t))
asyncio.run(c())
"@
Remove-Item Env:\GHL_API_KEY
Remove-Item Env:\GHL_LOCATION_ID
Write-Host "Tools registered: $ToolCount"
if ([int]$ToolCount -lt 70) {
    Write-Host "WARN: Expected ~78 tools, got $ToolCount" -ForegroundColor Yellow
}

# 6. Print config snippet (forward slashes work fine in JSON on Windows)
$JsonPath = $VenvPython -replace '\\', '/'
$ConfigPath = Join-Path $env:APPDATA "Claude\claude_desktop_config.json"

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Green
Write-Host ""
Write-Host "Add this to: $ConfigPath"
Write-Host "(merge the 'gohighlevel' entry into mcpServers if you have other servers)"
Write-Host ""
Write-Host "----------- COPY BELOW -----------" -ForegroundColor Yellow
@"
{
  "mcpServers": {
    "gohighlevel": {
      "command": "$JsonPath",
      "args": ["-m", "ghl_mcp"],
      "env": {
        "GHL_API_KEY": "REPLACE_WITH_YOUR_PIT_TOKEN",
        "GHL_LOCATION_ID": "REPLACE_WITH_YOUR_LOCATION_ID"
      }
    }
  }
}
"@
Write-Host "----------- COPY ABOVE -----------" -ForegroundColor Yellow
Write-Host ""
Write-Host "Agency owners: those two values are all you need — your agency/company ID"
Write-Host "is auto-detected at startup, so the agency tools (snapshots, SaaS, etc.)"
Write-Host "work without any extra config."
Write-Host ""
Write-Host "Open the config file in Notepad:"
Write-Host "  notepad `"$ConfigPath`""
Write-Host ""
Write-Host "Then quit Claude Desktop fully (right-click tray icon -> Quit) and reopen."
Write-Host ""
Write-Host "To update later, just re-run this script — it will git pull and reinstall."
