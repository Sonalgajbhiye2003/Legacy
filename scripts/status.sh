#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

docker compose ps

if docker compose exec -T db pg_isready -U odoo -d postgres >/dev/null 2>&1; then
    echo "PostgreSQL: healthy"
else
    echo "PostgreSQL: unavailable"
fi

if command -v curl >/dev/null 2>&1 && curl --fail --silent --output /dev/null --max-time 5 http://localhost:8069/web/login; then
    echo "Odoo HTTP: responsive"
else
    echo "Odoo HTTP: unavailable"
fi

if command -v ss >/dev/null 2>&1 && ss -ltn | grep -q ':8069 '; then
    echo "Port 8069: listening"
else
    echo "Port 8069: not confirmed"
fi
