# Legacy financial reports

Odoo 17 Enterprise reporting-only extension of `account_reports`.

Two native accounting reports retain the customer statement row order. Actuals use
native domain/aggregation expressions on posted journal items. The Balance Sheet
uses native unallocated earnings, plus explicitly mapped retained-equity accounts.
No report method creates journal entries, stock moves, or valuation layers.

Report managers configure company-scoped account and approved product mappings on
native report lines. Mapping changes regenerate only their native domain expressions.
Duplicate detail mappings are rejected; concurrent mapping changes are serialized
per report. Definitions have stable XML IDs and `noupdate`, so module upgrades do
not replace approved mappings or formulas.

All reports remain provisional while configuration/data decisions are unresolved.
Pending mappings are displayed as text, not zero. Coverage diagnostics count both
debit and credit, so offsetting omissions remain visible. Totals are partial until
all relevant coverage exceptions are resolved.

The native monthly budget source is disabled until approved. Budget external values
are dated on the first of each month, are company/expression/month unique, and
cannot override actual expressions. Missing months differ from explicit zero values.
Contribution denominators, variance signs, and prior-year period/YTD basis require
explicit configuration. Unapproved columns remain blank. Prior-year actuals and
drill-downs use a native forced-date column group. Analytic splits remain disabled
pending an approved allocation specification.

PDF and XLSX consume native report lines. The custom PDF template embeds scoped
body styles. XLSX adds the same provisional diagnostics and printable widths.

The Legacy Detailed Income Statement adds a supplemental production-material
section after Net Profit Margin and before Credit balance: raw materials consumed,
packaging consumed, and their total. These rows do not feed the existing Cost of
Sales, Gross Profit, or Net Profit calculations. Their actuals are the negative
company-currency sum of stock valuation layer values linked to completed
manufacturing component moves, classified by the report's raw-material and
packaging product-category roots. Returns/reversals use their own signed valuation
layers and move dates. No BOM estimate, purchase value, or current standard cost is
used. No matching moves is a genuine zero; missing or all-zero valuation for an
actual component move is displayed as Pending valuation. Category roots default
from `legacy_mrp_master_data` only when both report mappings are empty; existing
category choices are preserved by the migration. Drill-down opens the component
stock moves within the same company, date, category, and manufacturing scope.

Focused tests are tagged `legacy_finance_dev`, `post_install`, `-standard`, and
`-at_install`, and refuse to run outside `legacy_finance_validation_20260921`.
Run with `--test-tags=legacy_finance_dev`, never an unrestricted test selector.
The later integration matrix is documentation only and is not imported as tests.
No integration scenarios run through the developer selector.

The private local handover, customer source files, reconciliation, backup, and
configuration evidence are stored outside this repository. No production-readiness
or user-acceptance claim is made by this addon.
