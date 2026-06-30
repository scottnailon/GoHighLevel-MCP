#!/usr/bin/env bash
# Prompt for a GHL token (hidden), then list the locations it can access.
# Token is never echoed, never stored in shell history, never written to disk.
# Output goes to the screen AND /tmp/ghl-locs.txt as a fallback.
set -euo pipefail

cd "$(dirname "$0")/.."

printf 'Paste agency token (input hidden), then press Enter: ' >&2
IFS= read -rs TOKEN
printf '\n' >&2

if [ -z "${TOKEN:-}" ]; then
  echo "ERROR: no token entered." >&2
  exit 2
fi
case "$TOKEN" in
  *xxxx*|*your-full-token*|REPLACE_ME)
    echo "ERROR: that looks like the placeholder, not a real token." >&2
    exit 2 ;;
esac
case "$TOKEN" in
  pit-*) : ;;
  *) echo "WARNING: token does not start with 'pit-' — continuing anyway." >&2 ;;
esac

LOC="${GHL_LOCATION_ID:-}"
if [ -z "$LOC" ]; then
  echo "ERROR: set GHL_LOCATION_ID first so the agency can be resolved, e.g." >&2
  echo "  GHL_LOCATION_ID=your-location-id bash scripts/find_location.sh" >&2
  exit 2
fi
echo "Using GHL_LOCATION_ID=$LOC to resolve the agency..." >&2
echo "---"

GHL_API_KEY="$TOKEN" GHL_LOCATION_ID="$LOC" \
  venv/bin/python scripts/discover_locations.py 2>&1 | tee /tmp/ghl-locs.txt

echo "---"
echo "(Full output also saved to /tmp/ghl-locs.txt)" >&2
