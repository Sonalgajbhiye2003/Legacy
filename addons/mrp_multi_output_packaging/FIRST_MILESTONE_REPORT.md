# First Milestone Report

Date: 2026-07-20  
Database tested: `legacy_manufacturers_multi_output_dev`  
Module: `mrp_multi_output_packaging` version `17.0.1.0.0`

## Outcome

The quantity-and-packaging foundation is installed and tested on the isolated development clone. Standard Odoo manufacturing remains on its native workflow; Custom Multi-Output MOs gain a recipe-snapshot engine, finished output plan, consolidated packaging components, Soya Chunk bulk reconciliation, company tolerances, and completion blocking.

## Baseline protection

- Protected archive: `C:\Odoo\17\backups\before_multi_output_development\legacy_manufacturers_before_multi_output_20260720_131758.zip`
- Archive SHA-256: `728041ef3b752d18b4218294eb7f380d3484ce8194d69b80b55253cb835a1715`
- SHA-256 sidecar is stored beside the archive.
- Full clone created: `legacy_manufacturers_multi_output_dev`.
- Clone login and application menus verified in the browser.
- Original database restored from the checksum-verified protected archive after runtime bus/cron audit rows were detected.
- Final verification compared the restored original with a fresh temporary restore of the same archive: `ORIGINAL_LOGICAL_MATCH=PASS`.
- Final logical dump SHA-256: `b710964914083df433c18134c9f5e0ccbb6c3ba0a78297a6087bb33515f11ea3`.
- All 493 non-manifest archive members/filestore members were retained; the temporary comparison database was removed.
- Odoo 17 local cron threads are set to `0` to prevent the protected original from drifting through background jobs in this neutralized development environment.

## Files created

- Add-on root: `__init__.py`, `__manifest__.py`, `README.md`, `IMPLEMENTATION_NOTES.md`, this report.
- Models: `mrp_bom.py`, `mrp_production.py`, `mrp_production_output.py`, `mrp_packaging_recipe.py`, `product_product.py`, `stock_move.py`, `mrp_bom_byproduct.py`, `res_company.py`.
- Views: BoM, MO, packaging recipe, product variant, company, and menu XML files.
- Security: four groups, six company record rules, and access-control CSV.
- Data: packaging recipe sequence.
- Tests: common fixtures plus standard workflow, packaging recipe, multi-output quantity, and Soya Chunk reconciliation suites.
- Operational scripts under `C:\Odoo\17\scripts`: protected backup/clone, group/backfill, browser verification/cleanup, database audit, baseline restore, and logical verification.

## Models added

- `mrp.packaging.recipe`
- `mrp.packaging.recipe.line`
- `mrp.production.recipe.snapshot`
- `mrp.production.recipe.snapshot.line`
- `mrp.production.output.line`
- `mrp.production.packaging.line`

## Models extended

- `mrp.bom`: workflow and custom process type.
- `mrp.production`: workflow copy/lock, output and snapshot relations, packaging calculations, bulk reconciliation, tolerances/status, reload/recalculate actions, confirmation and completion hooks.
- `product.product`: variant-specific net content, bulk equivalent, default recipe/operation/work centre, recipe smart button.
- `stock.move`: component source, packaging expectations/variance, calculation drill-down, and standard by-product expected/actual/variance/reason fields.
- `mrp.bom.byproduct`: company variance threshold reference; native by-product generation is unchanged.
- `res.company`: warning/blocking and variance-reason tolerances.

## Views added

- Standard MO form inheritance with custom fields/tabs hidden when workflow is Standard.
- Custom MO reconciliation header, Finished Output Plan tab, Packaging Consumption tab, custom component metadata, and genuine by-product variance columns.
- BoM workflow fields.
- Product-variant Packaging tab and Packaging Recipes smart button.
- Packaging recipe list/form/search with chatter and version/effective dates.
- Company tolerance section.
- Manufacturing > Configuration > Packaging Recipes menu.

## Security groups

- Multi-Output Manufacturing User
- Multi-Output Manufacturing Supervisor
- Packaging Recipe Manager
- Multi-Output Cost Manager (reserved for the valuation phase)

Recipe, recipe-line, snapshot, output, and calculation records use allowed-company rules. User, supervisor, and recipe-manager permissions were exercised by automated access tests. No unrestricted `sudo()` is used in user-facing model workflows.

## Odoo methods inherited

- `mrp.production.action_confirm(self)`: custom preparation before `super()`; Standard branch untouched.
- `mrp.production._get_move_raw_values(self, product_id, product_uom_qty, product_uom, operation_id=False, bom_line=False)`: `super()` first, additive source metadata only.
- `mrp.production.pre_button_mark_done(self)`: scoped custom validation before `super()`, preserving Community, Shop Floor, and quality checks.

The following installed hooks were inspected but deliberately not overridden: `_get_moves_raw_values`, `_get_moves_finished_values`, `_get_move_finished_values`, `_create_update_move_finished`, `button_mark_done`, `_button_mark_done_sanity_checks`, `_split_productions`, `_action_confirm_mo_backorders`, and `action_cancel`. Exact signatures and ordering are recorded in `IMPLEMENTATION_NOTES.md`.

## Automated tests

Command used:

```text
C:\Odoo\17\venv\Scripts\python.exe C:\Odoo\17\community\odoo-bin -c C:\Odoo\17\odoo17.conf -d legacy_manufacturers_multi_output_dev -u mrp_multi_output_packaging --test-enable --test-tags /mrp_multi_output_packaging --stop-after-init --log-level=test
```

Final result:

```text
11 post-test methods in 7.41s
0 failed, 0 errors
```

Coverage includes:

- Standard BoM/MO confirmation, native main product and native by-product moves, process component source, and absence of custom rows.
- Recipe creation, effective date selection, overlap rejection, rounding, wastage, snapshots, and snapshot immutability.
- Duplicate output rejection and actual-quantity packaging refresh.
- Multi-company record rules and group access.
- Soya Chunk 100 g, 500 g, and 1 kg outputs: 800 kg packaged equivalent and 200 kg automatic primary bulk output.
- Six output-level packaging contributions consolidated to two component moves; common carton demand consolidated to 80 units with three linked contributions.
- Negative remaining bulk blocking and automatic packaging variance calculation.

## Manual browser verification

- Development login succeeded and the neutralization banner remained visible.
- Manufacturing, Shop Floor, Accounting, Sales, Purchase, Inventory, and HR applications remained available.
- Packaging Recipes appeared under Manufacturing > Configuration.
- Recipe list and editor rendered the required header, version/effective dates, material columns, and chatter.
- A temporary Draft custom MO rendered both workflow selections, reconciliation header, Finished Output Plan, and Packaging Consumption tabs.
- Its 100 x 500 g plan displayed 50 kg packaged equivalent and an automatic 50 kg Primary Bulk line.
- A Standard draft MO displayed only Components, Work Orders, By-Products, and Miscellaneous; custom tabs and component metadata columns were hidden.
- The temporary browser-verification MO, BoM, recipe, moves, and products were removed afterward.

## Regression and calculation results

- Standard MO regression: PASS. Standard confirmation and native by-product move generation remain intact; no custom output or packaging rows are generated.
- Custom MO calculation: PASS. Stored equivalents use Odoo UoM conversion within the same category.
- Packaging consolidation: PASS. Key includes product, UoM, operation, source location, and company, with output-level drill-down retained.
- Bulk reconciliation: PASS. Planned/actual packaged equivalent, loss, remaining bulk, difference, and balanced/warning/blocked status recalculate; one Primary Bulk line is maintained automatically.
- Genuine by-products: PASS. They remain native Odoo by-product finished moves with additive expected/actual/variance/reason display fields only.

## Final environment audit

- Original: 239 installed modules; `mrp_multi_output_packaging` absent; neutralized `true`.
- Development clone: 240 installed modules; `mrp_multi_output_packaging` installed; neutralized `true`.
- Existing mail-server state remained unchanged in both databases; no integration was activated.
- `Odoo17Local`: Running, Automatic; port 8077 returned HTTP 200.
- `odoo-server-19.0`: Running, Automatic; port 8069 returned HTTP 200.
- Odoo 19 was not stopped, upgraded, reconfigured, or modified.

## Known limitations and remaining phases

- Custom output lines are a milestone-1 planning/quantity engine; custom finished-output stock completion and valuation are intentionally not implemented.
- No custom cost allocation, accounting allocation, Soya Oil packaging completion, custom unbuild valuation, dashboards, or advanced reports.
- Consolidated packaging actuals can be entered on calculation lines and are refreshed from linked moves when actual outputs change; richer shop-floor allocation UX is a later phase.
- Custom output distribution across MO backorders is not added in milestone 1; native Odoo backorders remain protected.
- The Cost Manager group is present but has no valuation-specific permissions until the valuation phase.

## Definition of done

Milestone 1 is complete on `legacy_manufacturers_multi_output_dev`: the module installs, tests pass, browser layouts are verified, the original database is back at its protected logical baseline, the development clone remains neutralized, and Odoo 19 continues to operate independently.

## Functional retest — 2026-07-20

- Fresh module upgrade/test run: 11 post-test methods, 0 failures, 0 errors.
- Disposable confirmed MO verification: 2 output lines, 1 immutable recipe snapshot, 1 packaging calculation line, and 1 generated packaging component move.
- Confirmed UI values: planned usable 100 kg, actual usable 100 kg, packaged equivalent 50 kg, automatic bulk output 50 kg, reconciliation difference 0 kg, status Balanced.
- Components tab showed the generated 100-unit packaging move with source `Packaging Recipe`.
- Packaging Consumption showed planned and expected-actual demand of 100 units linked to the generated stock move.
- Completion validation correctly blocked the unexplained -100-unit packaging variance.
- All disposable MO, move, BoM, recipe, and product records were removed; final audit found 0 temporary test orders.
- Original database was restored and reverified after testing: `ORIGINAL_LOGICAL_MATCH=PASS`, logical SHA-256 unchanged.
- Final database audit: original 239 modules/custom module absent; development 240 modules/custom module installed; both neutralized.
- Both Odoo Windows services remain Running and Automatic.
