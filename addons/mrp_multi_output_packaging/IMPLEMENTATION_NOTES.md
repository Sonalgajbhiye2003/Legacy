# Odoo 17 implementation notes

These notes record the extension points inspected in the installed Odoo 17 source at `C:\Odoo\17\community` and `C:\Odoo\17\enterprise`. No signatures were copied from another Odoo version.

## BoM and onchange behaviour

- Model: `mrp.bom`, source `community/addons/mrp/models/mrp_bom.py`.
- Native fields retained: `product_tmpl_id`, `product_id`, `product_qty`, `product_uom_id`, `bom_line_ids`, `byproduct_ids`, `operation_ids`, `type`, `company_id`.
- Extension: additive fields `manufacturing_workflow` and `custom_process_type`; their onchange only clears the custom type when Standard is selected. All existing BoMs receive the `standard` default.
- Model: `mrp.production`; the installed BoM onchange creates/updates native raw and finished moves through `_create_update_move_raw()` and `_create_update_move_finished()`. The custom onchange copies only the workflow fields and does not replace native onchange logic.

## Confirmation and stock-move generation

| Installed model | Exact installed method signature | Custom order and reason |
|---|---|---|
| `mrp.production` | `action_confirm(self)` | Custom MOs validate, snapshot recipes, calculate packaging, and create draft packaging raw moves **before** `super()`. Native `super()` then confirms raw/finished moves, work orders, scheduler links, pickings, and MO state. Standard MOs execute `super()` with no custom records. |
| `mrp.production` | `_get_moves_raw_values(self)` | Inspected as the BoM explosion entry point. Not replaced. |
| `mrp.production` | `_get_move_raw_values(self, product_id, product_uom_qty, product_uom, operation_id=False, bom_line=False)` | `super()` is called first; only `component_source` metadata is added (`process_bom` when `bom_line`, otherwise `manual`). Packaging generation changes its own returned value to `packaging_recipe`. |
| `mrp.production` | `_get_moves_finished_values(self)` | Inspected and deliberately not overridden. It generates the main finished move and iterates native `bom_id.byproduct_ids`. This protects genuine Soya Oil by-products. |
| `mrp.production` | `_get_move_finished_values(self, product_id, product_uom_qty, product_uom, operation_id=False, byproduct_id=False, cost_share=0)` | Inspected and deliberately not overridden in milestone 1; there is no custom finished-output valuation or generated co-product move. |
| `mrp.production` | `_create_update_move_finished(self)` | Inspected and deliberately retained for standard onchange behaviour. |

Packaging moves are normal `stock.move` rows linked by `raw_material_production_id`. Consolidation uses the required key: packaging product, UoM, operation, source location, and company. Output-level calculation rows retain the contribution and link back to the consolidated move.

## Completion, cancellation, and backorders

| Installed model | Exact installed method signature | Custom order and reason |
|---|---|---|
| `mrp.production` | `pre_button_mark_done(self)` | Custom completion validation runs before `super()`. `super()` retains all serial/lot, consumption, quantity, backorder, work-order, and Enterprise Shop Floor/quality checks. Standard MOs skip custom validation. |
| `mrp.production` | `button_mark_done(self)` | Inspected; not overridden. Native pre-check, work-order finishing, backorder creation, inventory posting, state transition, allocation, and report actions remain intact. |
| `mrp.production` | `_button_mark_done_sanity_checks(self)` | Inspected; not overridden. Company and serial uniqueness checks remain active. |
| `mrp.production` | `_split_productions(self, amounts=False, cancel_remaining_qty=False, set_consumed_qty=False)` | Inspected in Community and Enterprise `mrp_workorder`; not overridden in milestone 1. Native backorder quantities and work-order quality state are retained. |
| `mrp.production` | `_action_confirm_mo_backorders(self)` | Inspected; not overridden. Enterprise quality extensions can continue creating checks for backorders. |
| `mrp.production` | `action_cancel(self)` | Inspected; not overridden. Generated packaging moves are part of `move_raw_ids`, so native cancellation handles them together with other components. Enterprise `quality_mrp.action_cancel()` still cleans pending checks. |

## Enterprise Shop Floor and quality

- `enterprise/mrp_workorder/models/mrp_production.py` inherits `mrp.production` and overrides:
  - `_split_productions(self, amounts=False, cancel_remaining_qty=False, set_consumed_qty=False)` with `super()` first, then backorder quality-component updates.
  - `pre_button_mark_done(self)` with `super()` first, then finished lot enforcement and work-order quality verification.
- `enterprise/quality_mrp/models/mrp_production.py` overrides `button_mark_done(self)` to require completed quality checks before `super()`.
- The module extends `pre_button_mark_done()` and calls `super()` after its scoped custom checks, preserving both Enterprise chains.

## Manufacturing accounting inspection and boundary

- Installed Community `mrp_account` extends `mrp.production` (with `analytic.mixin`) and implements `_cal_price(self, consumed_moves)`, `write(self, vals)`, and `_get_backorder_mo_vals(self)`. `_cal_price` allocates native finished/by-product cost using standard cost shares and work-centre cost.
- Installed Enterprise `mrp_account_enterprise` adds cost-structure and manufacturing analysis reports; `mrp_accountant` adds production-cost-account settings.
- `stock_account.models.stock_move._action_done(self, cancel_backorder=False)` is the installed valuation posting path.
- This module does not depend on `stock_account`, does not override valuation methods, does not allocate costs to custom output lines, and does not generate custom finished-output moves in milestone 1.

## Standard-behaviour protection

Every behavioural branch begins with `manufacturing_workflow == 'custom_multi_output'`. Defaults are Standard; custom pages are hidden for Standard MOs; custom output/packaging rows are never generated for Standard MOs. Native by-products, work orders, Shop Floor, quality, cancellation, backorders, inventory posting, and accounting remain on their installed Odoo paths.
