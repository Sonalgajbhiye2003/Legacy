#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
CONFIG_DIR="$ROOT_DIR/config"
CONFIG_FILE="$CONFIG_DIR/odoo.conf"

generate_secret() {
    local generated_secret=""
    if command -v python3 >/dev/null 2>&1 \
        && generated_secret="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))' 2>/dev/null)" \
        && [[ -n "$generated_secret" ]]; then
        printf '%s\n' "$generated_secret"
        return 0
    fi
    if command -v openssl >/dev/null 2>&1 \
        && generated_secret="$(openssl rand -base64 32 2>/dev/null | tr -d '\n')" \
        && [[ -n "$generated_secret" ]]; then
        printf '%s\n' "$generated_secret"
        return 0
    fi
    echo "ERROR: A working Python 3 or OpenSSL installation is required to generate secrets." >&2
    return 1
}

mkdir -p "$CONFIG_DIR"
umask 077

if [[ ! -e "$ENV_FILE" ]]; then
    postgres_password="$(generate_secret)"
    printf 'POSTGRES_PASSWORD=%s\n' "$postgres_password" > "$ENV_FILE"
    unset postgres_password
    chmod 600 "$ENV_FILE" 2>/dev/null || true
    echo "Created .env with a generated PostgreSQL password."
else
    echo "Preserved existing .env."
fi

if [[ ! -e "$CONFIG_FILE" ]]; then
    master_password="$(generate_secret)"
    {
        printf '[options]\n\n'
        printf 'addons_path = /usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons,/mnt/legacy-addons,/mnt/third-party-addons,/mnt/private-addons\n\n'
        printf 'data_dir = /var/lib/odoo\n\n'
        printf 'admin_passwd = %s\n\n' "$master_password"
        printf 'list_db = True\n\n'
        printf 'proxy_mode = True\n\n'
        printf 'log_level = info\n'
    } > "$CONFIG_FILE"
    unset master_password
    chmod 600 "$CONFIG_FILE" 2>/dev/null || true
    echo "Created config/odoo.conf with a generated Odoo master password."
else
    echo "Preserved existing config/odoo.conf."
fi

if grep -q 'REPLACE_WITH_GENERATED' "$ENV_FILE" "$CONFIG_FILE"; then
    echo "ERROR: An existing secret file still contains a template placeholder." >&2
    echo "Replace it manually or remove only that local file and rerun this script." >&2
    exit 1
fi

echo "Secret files are ready. Their values were not displayed."
