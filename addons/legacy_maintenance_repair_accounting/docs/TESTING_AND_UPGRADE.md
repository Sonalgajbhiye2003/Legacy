# Test Execution and Upgrade Notes

Focused suite:

```powershell
& C:\Odoo\17\venv\Scripts\python.exe C:\Odoo\17\community\odoo-bin -c C:\Odoo\17\odoo17.conf -d <test_db> -u legacy_maintenance_repair_accounting,legacy_maintenance_repair_asset --test-enable --test-tags /legacy_maintenance_repair_accounting --stop-after-init --no-http
```

Fresh installation uses `-i` in place of `-u`. Run on a disposable database. Review the Odoo log for tracebacks, failed tests, missing XML IDs, access warnings, and unbalanced entries.

Upgrade requires a normal module upgrade because fields, SQL constraints, record rules, and the reconciliation SQL view are created by the ORM. Existing records default to safe draft/not-posted states and require Finance review before processing. Back up the database and filestore first. The optional Assets bridge is auto-installed only where both the core and `account_asset` are installed.

Known limitations: partial material returns are valued proportionally to the original issue; asset depreciation parameters come from the configured Asset Model or remain draft for Finance completion; reconciliation is company-currency based; historical records created before integration may require explicit linking/classification.
