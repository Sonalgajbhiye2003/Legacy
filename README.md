# Legacy Odoo Sandbox

## Purpose

This private repository provides a zero-cost Odoo 17 development and temporary UAT sandbox for the Legacy implementation. It runs inside GitHub Codespaces with Docker Compose and is not production hosting.

## Architecture

- GitHub Codespaces development container with Docker and Docker Compose
- Odoo 17 on forwarded port `8069`
- PostgreSQL 15
- Existing Legacy modules mounted from `addons/`
- Reviewed third-party modules mounted from `third_party_addons/`
- Optional additional modules in `custom_addons/`
- Untracked licensed modules mounted from `private_addons/`
- Named Docker volume `legacy-db-data` for PostgreSQL
- Named Docker volume `legacy-odoo-data` for the Odoo filestore and attachments

The Codespaces URL has the form `https://<codespace-name>-8069.app.github.dev`. Port `8069` is private by default.

## First Start

Codespaces runs the bootstrap automatically after creating the development container. To run it again manually:

```bash
./scripts/bootstrap.sh
```

The bootstrap generates `.env` and `config/odoo.conf` only when missing, starts PostgreSQL and Odoo, waits for both services, and preserves existing secrets.

## Normal Start

```bash
./scripts/start.sh
```

## Stop

```bash
./scripts/stop.sh
```

This stops the containers without deleting data.

## Status

```bash
./scripts/status.sh
```

## Logs

```bash
./scripts/logs.sh
```

## Custom Modules

The repository already contains Legacy modules in `addons/` and reviewed dependencies in `third_party_addons/`. Place any additional private Odoo 17 modules in `custom_addons/`. The container exposes these as:

```text
/mnt/extra-addons
/mnt/legacy-addons
/mnt/third-party-addons
/mnt/private-addons
```

Update the Apps list after adding a module. Put licensed Odoo Enterprise and other non-redistributable dependencies in `private_addons/`; its contents are Git ignored. Never force-add licensed source to this repository.

## Restore Legacy Database

Keep Codespaces port `8069` **Private** during restore.

Before restoring the Legacy database, supply all licensed dependencies used by that database in `private_addons/`. The current module audit identified `mrp_maintenance`, `account_asset`, `mrp_workorder`, and `to_base` as unavailable from the Community image/repository.

1. Start the sandbox with `./scripts/bootstrap.sh`.
2. Open the private forwarded URL and browse to `/web/database/manager`.
3. Select **Restore Database**.
4. Upload the Legacy ZIP backup directly from secure local storage.
5. Restore it as `legacy_sandbox`.

Never copy the backup into Git. As an alternative for a large dump, copy it temporarily into the running Codespace outside the repository and restore with PostgreSQL tools, then delete the temporary copy.

## Lock Down Database Manager

After the restore and login test, lock Odoo to the restored database while preserving the generated master password:

```bash
./scripts/lockdown-uat.sh legacy_sandbox
./scripts/security-check.sh
```

This applies:

```ini
dbfilter = ^legacy_sandbox$
list_db = False
```

The database manager must remain disabled before public UAT access.

## Expose UAT Publicly

Only after the database is restored, login is verified, and `./scripts/security-check.sh` passes:

1. Open the Codespaces **PORTS** panel.
2. Find port `8069`.
3. Change **Port Visibility** to **Public**.
4. Share the generated `https://<codespace-name>-8069.app.github.dev` URL temporarily.
5. Return the port to **Private** when UAT ends.

Public exposure is intentionally not automated.

## Codespaces Limitation

GitHub Codespaces is used for development and temporary UAT, not production. The environment may stop when the Codespace stops, and free usage is subject to the account's Codespaces quota. Docker volumes persist across ordinary container restarts but must not be treated as the only backup.

> **DATA LOSS WARNING:** Never run `docker compose down -v` unless permanent deletion is intended. Removing `legacy-db-data` deletes PostgreSQL data. Removing `legacy-odoo-data` deletes the Odoo filestore and uploaded attachments. A usable backup requires both database and filestore data.

## Security

Never commit:

- `.env`
- `config/odoo.conf`
- database backups or customer data
- passwords, API keys, or credentials
- Odoo filestore contents

The committed `.env.example` and `config/odoo.conf.example` contain placeholders only. Run `./scripts/generate-secrets.sh` to create local runtime secrets without printing their values.

## Current Add-ons

- `legacy_maintenance_repair_accounting`
- `legacy_maintenance_repair_asset`
- `legacy_mrp_labour_cost`
- `legacy_mrp_master_data`
- `legacy_purchase_approval`
- `legacy_ui_icon_fix`
- `mrp_multi_output_packaging`
- `stock_request`
- `impersonate_login`
- `web_chatter_position_cr`

Some modules depend on licensed Odoo Enterprise or separately licensed add-ons. Supply those in the Git-ignored `private_addons/` directory before installing the dependent modules or restoring the Legacy database. The infrastructure does not modify or fabricate those dependencies.
