#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: Docker is not available." >&2
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "ERROR: Docker Compose v2 is not available." >&2
    exit 1
fi

mkdir -p custom_addons private_addons config
"$ROOT_DIR/scripts/generate-secrets.sh"

docker compose config --quiet
docker compose up -d

echo "Waiting for PostgreSQL..."
database_ready=false
for _ in $(seq 1 60); do
    if docker compose exec -T db pg_isready -U odoo -d postgres >/dev/null 2>&1; then
        database_ready=true
        break
    fi
    sleep 2
done

if [[ "$database_ready" != true ]]; then
    echo "ERROR: PostgreSQL did not become healthy in time." >&2
    docker compose ps
    exit 1
fi

echo "Waiting for Odoo on http://localhost:8069..."
odoo_ready=false
for _ in $(seq 1 90); do
    if command -v curl >/dev/null 2>&1; then
        if curl --fail --silent --show-error --output /dev/null --max-time 5 http://localhost:8069/web/login 2>/dev/null; then
            odoo_ready=true
            break
        fi
    elif python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8069/web/login', timeout=5)" >/dev/null 2>&1; then
        odoo_ready=true
        break
    fi
    sleep 2
done

if [[ "$odoo_ready" != true ]]; then
    echo "ERROR: Odoo did not become responsive in time." >&2
    docker compose ps
    docker compose logs --tail=100 odoo
    exit 1
fi

docker compose ps
echo "Legacy Odoo 17 sandbox is ready on port 8069. Codespaces visibility remains private."
