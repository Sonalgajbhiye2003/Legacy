# Legacy MRP Master Data - Data Quality Report

## Source Files
- `C:\Users\SONAL\OneDrive\Desktop\Legacy Group Docs\June 26 stock sheet.xlsx`
- `C:\Users\SONAL\OneDrive\Desktop\Legacy Group Docs\Legacy products  BOM-July 26.xlsx`
- `C:\Users\SONAL\OneDrive\Desktop\Legacy Group Docs\OPS010-Process Flow Diagrams.xlsx`

## Summary
- Total source product lines: 71
- Total unique products created: 82
- Duplicates merged: 1
- Products requiring review: 9
- Total BOM sheets: 16
- Valid active BOMs: 3
- Inactive/incomplete BOMs: 13
- Formula-derived quantity cells reviewed: 57
- Work centers created: 4
- Operations created: 147
- Packaging recipes created: 16

## Product Counts by Category
- Raw Materials: 15
- Packaging Materials: 31
- Work in Progress: 14
- By-products: 5
- Finished Goods: 17

## Manufacturing Architecture
The addon uses the existing `mrp_multi_output_packaging` module as the single source of packaging consumption. BoM component lines contain process/raw components only. Packaging materials are configured in `mrp.packaging.recipe`, where the custom module snapshots recipes on MO confirmation and creates consolidated raw stock moves with `component_source = packaging_recipe`. This avoids consuming packaging both through standard BoM lines and the custom packaging logic.

## Active BOMs
- Instant Porridge - Box (20 x 500g): source sheet `Instant porridge 500g`, bulk product `Bulk Instant Porridge`, output equivalent 10.0 kg.
- TSP - Case (10 x 700g): source sheet `TSP 700g x 10`, bulk product `Bulk TSP`, output equivalent 7.0 kg.
- TSP - 8kg Woven Bag: source sheet `TSP 8Kg`, bulk product `Bulk TSP`, output equivalent 8.0 kg.

## Inactive / Incomplete BOMs
- Instant Porridge - Box (10 x 1kg): source sheet `Instant porridge 1Kg` - Known source workbook problem requiring validation.
- Instant Porridge - 10kg Bag: source sheet `Instant porridge 10Kg` - Known source workbook problem requiring validation.
- Instant Porridge - 50kg Bag: source sheet `Instant porridge 50Kg` - Instant Porridge 50kg refers to Outer Bags - 90g.
- Instant Porridge - Box (8 x 500g): source sheet `Instant porridge boxed` - Known source workbook problem requiring validation.
- Instant Thobwa - Case (50 x 50g): source sheet `Instant thobwa` - Known source workbook problem requiring validation.
- Instant Thobwa - 25kg Bag: source sheet `Instant thobwa-25Kg` - Known source workbook problem requiring validation.
- TSP - Case (20 x 90g): source sheet `TSP 90g` - Known source workbook problem requiring validation.
- TSP - Case (5 x 700g): source sheet `TSP 700g x5` - TSP Case (5 x 700g) contains 7kg of soya beans although packed output appears to be 3.5kg.
- TSP - 3kg Bag: source sheet `TSP 3Kg` - TSP 3kg contains an outer-packaging quantity of zero.
- TSP - 3kg Woven Bag: source sheet `TSP 3Kg woven` - TSP 3kg woven contains generic outer-packaging quantity of zero.
- Puffs - Case (50 x 16g): source sheet `16g Corn puffs` - Known source workbook problem requiring validation.
- Zed Crunch Puffs Case (6 x 22): source sheet `Corn sticks` - Known source workbook problem requiring validation.
- Puffs - Case (30 x 60g): source sheet `60g x30 Corn puffs` - Known source workbook problem requiring validation.

## Duplicates Merged
- Row 52: `Inner liner-10Kg` merged into `Inner Liner - 10kg` in Packaging Materials.

## Formula / Quantity Review
No cached Excel error tokens were found, but several quantities are external workbook formulas. Active BOMs only use positive cached numeric values; known-problem sheets remain inactive even when Excel exposes a cached value.
- `Instant porridge 500g` row 5 `Maize` uses formula `='[1]Instant porridge 500g'!$I$5` with cached value `6.471910112359551`.
- `Instant porridge 500g` row 6 `Soya Beans` uses formula `='[1]Instant porridge 500g'!$I$6` with cached value `2.51685393258427`.
- `Instant porridge 500g` row 7 `Sugar` uses formula `='[1]Instant porridge 500g'!$I$7` with cached value `0.9363295880149813`.
- `Instant porridge 500g` row 8 `Salt` uses formula `='[1]Instant porridge 500g'!$I$8` with cached value `0.06516853932584268`.
- `Instant porridge 500g` row 9 `Sweetener` uses formula `='[1]Instant porridge 500g'!$I$9` with cached value `0.0026217228464419477`.
- `Instant porridge 1Kg` row 5 `Maize` uses formula `='[1]Instant porridge 500g'!$I$5` with cached value `6.471910112359551`.
- `Instant porridge 1Kg` row 6 `Soya Beans` uses formula `='[1]Instant porridge 500g'!$I$6` with cached value `2.51685393258427`.
- `Instant porridge 1Kg` row 7 `Sugar` uses formula `='[1]Instant porridge 500g'!$I$7` with cached value `0.9363295880149813`.
- `Instant porridge 1Kg` row 8 `Salt` uses formula `='[1]Instant porridge 500g'!$I$8` with cached value `0.06516853932584268`.
- `Instant porridge 1Kg` row 9 `Sweetener` uses formula `='[1]Instant porridge 500g'!$I$9` with cached value `0.0026217228464419477`.
- `Instant porridge 10Kg` row 5 `Maize` uses formula `='[1]Instant porridge 500g'!$I$5` with cached value `6.471910112359551`.
- `Instant porridge 10Kg` row 6 `Soya Beans` uses formula `='[1]Instant porridge 500g'!$I$6` with cached value `2.51685393258427`.
- `Instant porridge 10Kg` row 7 `Sugar` uses formula `='[1]Instant porridge 500g'!$I$7` with cached value `0.9363295880149813`.
- `Instant porridge 10Kg` row 8 `Salt` uses formula `='[1]Instant porridge 500g'!$I$8` with cached value `0.06516853932584268`.
- `Instant porridge 10Kg` row 9 `Sweetener` uses formula `='[1]Instant porridge 500g'!$I$9` with cached value `0.0026217228464419477`.
- `Instant porridge boxed` row 5 `Maize` uses formula `='[1]Instant porridge 500g'!$I$5` with cached value `6.471910112359551`.
- `Instant porridge boxed` row 6 `Soya Beans` uses formula `='[1]Instant porridge 500g'!$I$6` with cached value `2.51685393258427`.
- `Instant porridge boxed` row 7 `Sugar` uses formula `='[1]Instant porridge 500g'!$I$7` with cached value `0.9363295880149813`.
- `Instant porridge boxed` row 8 `Salt` uses formula `='[1]Instant porridge 500g'!$I$8` with cached value `0.06516853932584268`.
- `Instant porridge boxed` row 9 `Sweetener` uses formula `='[1]Instant porridge 500g'!$I$9` with cached value `0.0026217228464419477`.
- `Instant thobwa` row 5 `Maize` uses formula `='[1]Instant thobwa'!$J$6` with cached value `1.9636363636363638`.
- `Instant thobwa` row 6 `Soya Beans` uses formula `='[1]Instant thobwa'!$J$7` with cached value `0.19090909090909092`.
- `Instant thobwa` row 7 `Sugar` uses formula `='[1]Instant thobwa'!$J$8` with cached value `0.3409090909090909`.
- `Instant thobwa` row 8 `Salt` uses formula `='[1]Instant thobwa'!$J$9` with cached value `0.025`.
- `Instant thobwa` row 9 `Sweetener` uses formula `='[1]Instant thobwa'!$J$10` with cached value `0.001931818181818182`.
- `Instant thobwa-25Kg` row 5 `Maize` uses formula `='[1]Instant thobwa-25Kg'!$J$6` with cached value `19.636363636363637`.
- `Instant thobwa-25Kg` row 6 `Soya Beans` uses formula `='[1]Instant thobwa-25Kg'!$J$7` with cached value `1.9090909090909092`.
- `Instant thobwa-25Kg` row 7 `Sugar` uses formula `='[1]Instant thobwa-25Kg'!$J$8` with cached value `3.409090909090909`.
- `Instant thobwa-25Kg` row 8 `Salt` uses formula `='[1]Instant thobwa-25Kg'!$J$9` with cached value `0.25`.
- `Instant thobwa-25Kg` row 9 `Sweetener` uses formula `='[1]Instant thobwa-25Kg'!$J$10` with cached value `0.01931818181818182`.
- `TSP 90g` row 5 `Soya Beans` uses formula `='[1]TSP 90g'!$I$6` with cached value `1.7999999999999998`.
- `TSP 90g` row 6 `Beef Soya Spice` uses formula `='[1]TSP 90g'!$I$7` with cached value `0.16`.
- `TSP 90g` row 7 `Soya Beef Spice Rolls` uses formula `='[1]TSP 90g'!$I$8` with cached value `0.00054`.
- `TSP 90g` row 8 `TSP Rolls - 90g` uses formula `='[1]TSP 90g'!$I$9` with cached value `0.04`.
- `16g Corn puffs` row 5 `Breakfast Meal` uses formula `='[1]16g Corn puffs'!$I$5` with cached value `0.7246376811594203`.
- `16g Corn puffs` row 6 `Sunset Yellow` uses formula `='[1]16g Corn puffs'!$I$6` with cached value `0.0014492753623188408`.
- `16g Corn puffs` row 7 `Salt` uses formula `='[1]16g Corn puffs'!$I$7` with cached value `0.00481159420289855`.
- `16g Corn puffs` row 8 `Calcium Carbonate` uses formula `='[1]16g Corn puffs'!$I$8` with cached value `0.0007246376811594204`.
- `16g Corn puffs` row 9 `Baking Powder` uses formula `='[1]16g Corn puffs'!$I$9` with cached value `0.0014492753623188408`.
- `16g Corn puffs` row 10 `Cooking Oil` uses formula `='[1]16g Corn puffs'!$I$10` with cached value `0.052173913043478265`.
- Additional formula-derived cells omitted from report body: 17. See source workbook.

## Missing Work-Center Parameters
Legacy has not provided capacity, setup time, cleanup time, hourly cost, efficiency, or shift calendars. The addon uses safe Odoo defaults: capacity 1, efficiency 100%, setup/cleanup/hourly cost 0.

## Packaging Module Compatibility Result
- Packaging products are identified by `product.product.packaging_enabled` on packaged finished products and recipe lines on `mrp.packaging.recipe`.
- Packaging quantities are calculated from recipe `qty_per_base / base_qty`, output planned/actual quantities, wastage, and rounding method.
- Packaging moves are added to the same manufacturing order before native confirmation as raw moves with `component_source = packaging_recipe`.
- Packaging comes from custom recipe configuration, not from standard BoM lines in this addon.
- Draft packaging recipe moves are deleted and rebuilt during recalculation, preventing duplicate packaging consumption.
- Partial production/backorder behavior is handled by the existing module and native Odoo chains; this addon does not override it.

## Remaining Customer Decisions
- Outer Bags - 90g: BOM-only or mismatched packaging name; do not merge with Woven Bag - 90g without confirmation.
- Outer Packaging: Generic packaging name appears without pack size; do not merge with pack-specific outer packaging.
- Sticker: BOM-only packaging component not found in stock sheet.
- Inner Packaging - Zed Crunch: BOM-only/mismatched packaging name; stock sheet has Zed crunchy corn sticks inner packaging.
- Zambia Sugar Baler: BOM-only packaging/handling item not found in stock sheet.
- Outer Packaging - 60g: BOM-only packaging component not found in stock sheet.
- Zed Crunch Puffs Case (6 x 22): Finished product naming conflicts with Corn Sticks; do not merge automatically.
- Corn Sticks: Finished product name conflicts with Zed Crunch Puffs Case output description.
- Water: Not found as stock-controlled material in stock sheet.
- Woven Bag - 25kg versus Woven Bag - 50kg: Instant Thobwa 25kg refers to Woven Bag - 50kg; requires confirmation.
- Confirm by-product output quantities and operations before adding BoM by-product lines.
- Confirm process losses and yield percentages.
