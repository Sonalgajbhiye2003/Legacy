#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
failures=0

pass() { printf 'PASS: %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1" >&2; failures=$((failures + 1)); }

if [[ -f config/odoo.conf ]] && grep -Eiq '^[[:space:]]*list_db[[:space:]]*=[[:space:]]*False[[:space:]]*$' config/odoo.conf; then
    pass "Odoo database listing is disabled"
else
    fail "Set list_db = False after restoring the UAT database"
fi

if [[ -f config/odoo.conf ]] && grep -Eiq '^[[:space:]]*dbfilter[[:space:]]*=[[:space:]]*\^.+\$[[:space:]]*$' config/odoo.conf; then
    pass "An anchored dbfilter is configured"
else
    fail "Configure an anchored dbfilter after restoring the UAT database"
fi

git check-ignore -q .env && pass ".env is Git ignored" || fail ".env is not Git ignored"
git check-ignore -q config/odoo.conf && pass "Runtime odoo.conf is Git ignored" || fail "config/odoo.conf is not Git ignored"

tracked_backups="$(git ls-files '*.sql' '*.dump' '*.backup' '*.zip')"
if [[ -z "$tracked_backups" ]]; then
    pass "No database backup formats are tracked"
else
    fail "Tracked database backup files exist"
fi

if git ls-files --error-unmatch .env >/dev/null 2>&1 \
    || git ls-files --error-unmatch config/odoo.conf >/dev/null 2>&1; then
    fail "A runtime secret file is tracked"
else
    pass "Runtime secret files are not tracked"
fi

suspicious_files=""
candidate_files="$(git grep -Il -E '(admin_passwd|POSTGRES_PASSWORD|db_password|api[_-]?key|secret[_-]?key)[[:space:]]*[:=][[:space:]]*[^[:space:]]+' -- . ':!*.md' ':!*.rst' ':!*.po' ':!*.pot' 2>/dev/null || true)"
while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    case "$file" in
        .env.example|config/odoo.conf.example|scripts/generate-secrets.sh|scripts/security-check.sh|*/tests/*) continue ;;
    esac
    if git show ":$file" 2>/dev/null \
        | grep -Ei '(admin_passwd|POSTGRES_PASSWORD|db_password|api[_-]?key|secret[_-]?key)[[:space:]]*[:=][[:space:]]*[^[:space:]]+' \
        | grep -Eiv 'REPLACE_WITH|\$\{|example|dummy|test' >/dev/null; then
        suspicious_files="${suspicious_files}${file}\n"
    fi
done <<< "$candidate_files"

if [[ -z "$suspicious_files" ]]; then
    pass "No obvious plaintext credentials were detected in tracked files"
else
    fail "Possible plaintext credentials exist in tracked files (values were not displayed)"
    printf '%b' "$suspicious_files" | sed 's/^/  file: /' >&2
fi

if grep -Eq '"visibility"[[:space:]]*:[[:space:]]*"private"' .devcontainer/devcontainer.json; then
    pass "Codespaces port 8069 defaults to private"
else
    fail "Codespaces port 8069 is not explicitly private"
fi

repository="${GITHUB_REPOSITORY:-}"
if [[ -z "$repository" ]]; then
    remote_url="$(git remote get-url techbyteodoo 2>/dev/null || git remote get-url origin 2>/dev/null || true)"
    repository="$(printf '%s' "$remote_url" | sed -E 's#^https://github.com/##; s#^git@github.com:##; s#\.git$##')"
fi

if command -v gh >/dev/null 2>&1 && [[ -n "$repository" ]]; then
    visibility="$(gh repo view "$repository" --json visibility --jq .visibility 2>/dev/null || true)"
    if [[ "$visibility" == "PRIVATE" ]]; then
        pass "GitHub repository is private"
    else
        fail "Unable to verify the intended GitHub repository as private"
    fi
else
    echo "WARN: GitHub repository visibility could not be verified in this environment."
fi

if (( failures > 0 )); then
    printf 'Security check failed with %d issue(s).\n' "$failures" >&2
    exit 1
fi

echo "Security check passed. Port 8069 may now be considered for temporary public UAT access."
