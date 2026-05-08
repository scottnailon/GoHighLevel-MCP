#!/bin/bash
# GHL MCP v2 — Mac install script for Claude Desktop
# Clones the repo and installs to ~/.claude/mcp-servers/gohighlevel/
#
# Usage:
#   bash install_mac.sh
#
# To switch to GitHub after migration, update REPO_URL below.

set -euo pipefail

REPO_URL="https://github.com/scottnailon/GoHighLevel-MCP.git"
INSTALL_DIR="$HOME/.claude/mcp-servers/gohighlevel"

echo "=== GHL MCP v2 installer (Mac) ==="
echo ""

# 1. Check prerequisites
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install with: brew install python@3.12"
    exit 1
fi
PY_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
PY_VERSION="${PY_MAJOR}.${PY_MINOR}"
echo "Python: $PY_VERSION"
if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
    echo "ERROR: Python 3.10+ required. Install with: brew install python@3.12"
    exit 1
fi

if ! command -v git &>/dev/null; then
    echo "ERROR: git not found. Install Xcode Command Line Tools: xcode-select --install"
    exit 1
fi

# 2. Clone or update
echo ""
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Existing install found — pulling latest..."
    git -C "$INSTALL_DIR" pull --ff-only
else
    echo "Cloning from $REPO_URL ..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

# 3. Venv + install
echo ""
echo "Setting up venv..."
cd "$INSTALL_DIR"
python3 -m venv venv
source venv/bin/activate
echo "Installing dependencies..."
pip install -e . --quiet --upgrade-strategy eager

# 4. Smoke test
echo ""
echo "=== Smoke test ==="
TOOL_COUNT=$(GHL_API_KEY=test GHL_LOCATION_ID=test python -c "
import asyncio
from ghl_mcp.server import mcp
async def c():
    t = await mcp.list_tools()
    print(len(t))
asyncio.run(c())
" 2>/dev/null)
echo "Tools registered: $TOOL_COUNT"
if [ "$TOOL_COUNT" -lt 70 ] 2>/dev/null; then
    echo "WARN: Expected ~78 tools, got $TOOL_COUNT — install may be incomplete"
fi

# 5. Print config snippet
PYTHON_PATH="$INSTALL_DIR/venv/bin/python"
echo ""
echo "=== Done ==="
echo ""
echo "Add this to: ~/Library/Application Support/Claude/claude_desktop_config.json"
echo "(merge the 'gohighlevel' entry into mcpServers if you have other servers)"
echo ""
echo "----------- COPY BELOW -----------"
cat <<JSON
{
  "mcpServers": {
    "gohighlevel": {
      "command": "$PYTHON_PATH",
      "args": ["-m", "ghl_mcp"],
      "env": {
        "GHL_API_KEY": "REPLACE_WITH_YOUR_PIT_TOKEN",
        "GHL_LOCATION_ID": "REPLACE_WITH_YOUR_LOCATION_ID"
      }
    }
  }
}
JSON
echo "----------- COPY ABOVE -----------"
echo ""
echo "Open the config file with:"
echo "  open -e ~/Library/Application\\ Support/Claude/claude_desktop_config.json"
echo ""
echo "Then quit Claude Desktop (⌘Q) and reopen."
echo ""
echo "To update later, just re-run this script — it will git pull and reinstall."
