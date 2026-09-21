# Financial reports: read-only implementation checkpoint

This change starts the Balance Sheet/P&L implementation by identifying actual local accounting configuration before modifying balances. It does not install either report or change any journal, valuation, account mapping or business workflow. Production certification remains blocked pending local Odoo integration tests and reconciliation.

## Local execution

Use the existing Odoo 17 Python, odoo-bin and configuration. Start an Odoo shell for `odoo17_legacy_masterdata_dev`, without install or upgrade flags. The repository documents `C:\Odoo\17\community`, `C:\Odoo\17\enterprise` and deployed custom addons at `C:\Odoo\17\custom_addons`; verify the actual Python/configuration paths locally.

In the Odoo shell:

```python
from pathlib import Path
p = Path(r"C:\path\to\Legacy\tools\legacy_finance_preflight.py")
exec(compile(p.read_text(encoding="utf-8"), str(p), "exec"), {"env": env, "__name__": "__main__", "__file__": str(p)})
```

Audit queries use a separate PostgreSQL READ ONLY, REPEATABLE READ transaction and always roll back. No sudo or business-record posting/write calls are used. Custom code executed during ordinary Odoo startup is outside that audit transaction; use the known environment without `-i` or `-u`.

Default cut-off is 2025-12-31; set `LEGACY_AUDIT_DATE` for another date. Output defaults to the user's `LegacyLocalAudit` directory outside Git. An existing output is never overwritten. Output contains financial data and source paths; review it before sharing. Never commit output, customer workbooks, logs, credentials or database backups.

## Evidence collected

Installed modules; company-specific accounts, currency and fiscal dates; posted account-level trial balance and fiscal-year P&L; revenue without product references; category valuation/account settings; zero-current-cost products for review; valuation layers lacking direct accounting links for review; actual custom integration fields; posting override signatures; native report definitions and expressions.

A zero current product cost is not proof of zero historical valuation. A valuation layer creation/current timestamp is not a historical GL accounting date. Related adjustment layers and valuation-policy changes can explain some missing direct journal links. The tool does not call these diagnostics proven errors. A balanced trial balance is not certification of report completeness or mapping correctness. All requested workflow tests remain NOT_RUN.

## Offline tests

```text
python -m unittest discover -s tests -p test_legacy_finance_preflight.py -v
```

21 offline unit tests pass for numeric safeguards, privacy, version/database rejection, and read-only transaction handling using mocks. No Odoo integration test or live report test has run in the remote authoring environment.

## Remaining implementation

Inspect the actual installed requisition/repair/labour/CAPEX addons and Enterprise report API locally. Work on a restored staging database. Reuse native `account.report` lines, expressions, earnings handling and exports; no parallel report engine, no account-group hierarchy. Map and reconcile the two customer layouts, then add only demonstrated mixed-column/budget/styling gaps. Correct proven posting gaps in their existing owning addons, never by forcing report values.

Cover sales/credit notes, purchase/returns/landed costs, manufacturing outputs/by-products/packaging, write-offs, internal transfers, requisitions, repairs, quality, expenses, labour recovery, CWIP, PPE, depreciation, taxes, FX and earnings allocations. An owned internal transfer ordinarily has no P&L effect, and a quality check/hold or requisition approval does not by itself create a loss/expense. Post the actual financial event once and reconcile its journal items into both reports. Do not switch inventory valuation or change old journals automatically.

References:
- https://github.com/odoo/odoo/blob/17.0/addons/account/models/account_report.py
- https://github.com/odoo/odoo/blob/17.0/addons/stock_account/models/stock_move.py
