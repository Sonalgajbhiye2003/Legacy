#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="$ROOT_DIR/config/odoo.conf"
DATABASE_NAME="${1:-legacy_sandbox}"

if [[ ! "$DATABASE_NAME" =~ ^[A-Za-z0-9_]+$ ]]; then
    echo "ERROR: Database name may contain only letters, numbers, and underscores." >&2
    exit 1
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "ERROR: Run ./scripts/generate-secrets.sh first." >&2
    exit 1
fi

TEMP_FILE="$(mktemp)"
trap 'rm -f "$TEMP_FILE"' EXIT

awk -v db="$DATABASE_NAME" '
BEGIN { list_seen = 0; filter_seen = 0 }
/^[[:space:]]*list_db[[:space:]]*=/ { print "list_db = False"; list_seen = 1; next }
/^[[:space:]]*dbfilter[[:space:]]*=/ { print "dbfilter = ^" db "$"; filter_seen = 1; next }
{ print }
END {
    if (!list_seen) print "list_db = False"
    if (!filter_seen) print "dbfilter = ^" db "$"
}
' "$CONFIG_FILE" > "$TEMP_FILE"

chmod 600 "$TEMP_FILE" 2>/dev/null || true
mv "$TEMP_FILE" "$CONFIG_FILE"
trap - EXIT

echo "UAT database lockdown configured for $DATABASE_NAME."
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    cd "$ROOT_DIR"
    docker compose restart odoo
    echo "Odoo restarted with database manager disabled."
else
    echo "Restart Odoo when Docker is available."
fi
