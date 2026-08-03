# Legacy MRP Master Data

This addon installs manufacturing master data for Legacy Manufacturing on Odoo 17 using the three customer workbooks in `C:\Users\SONAL\OneDrive\Desktop\Legacy Group Docs`.

## Functional Design

The database uses one company, one physical plant, and one logical main warehouse. Four production-line work centers are created for TSP, Instant Thobwa, Instant Porridge, and Corn Puffs.

## Selected Manufacturing Architecture

The addon uses integrated production and packaging with the existing `mrp_multi_output_packaging` module. BoMs contain process/raw components only. Packaging materials are configured in packaging recipes so the custom module creates packaging stock moves exactly once on manufacturing order confirmation.

## Packaging Module Integration

The existing module identifies packaged products with `product.product.packaging_enabled`, stores package net content and bulk equivalent product on the product variant, and stores packaging consumption on `mrp.packaging.recipe`. During custom MO confirmation it snapshots the effective recipe, calculates packaging quantities, consolidates packaging raw moves, and marks them with `component_source = packaging_recipe`.

## Installation Prerequisites

Install `mrp_multi_output_packaging`, `purchase_stock`, and `mrp_workorder` first. Zambia accounting localization may remain installed; this addon does not change the chart of accounts.

## Installation Command

```powershell
& 'C:\Odoo\17\venv\Scripts\python.exe' 'C:\Odoo\17\community\odoo-bin' -c 'C:\Odoo\17\odoo17.conf' -d odoo17_legacy_masterdata_dev -i legacy_mrp_master_data --stop-after-init
```

## Upgrade Command

```powershell
& 'C:\Odoo\17\venv\Scripts\python.exe' 'C:\Odoo\17\community\odoo-bin' -c 'C:\Odoo\17\odoo17.conf' -d odoo17_legacy_masterdata_dev -u legacy_mrp_master_data --stop-after-init
```

## Import Order

1. Product categories
2. Products
3. Warehouse and locations
4. Work centers
5. BoM headers
6. BoM operations
7. BoM component lines
8. By-products
9. Quality control points
10. Packaging configuration

## Master-Data Verification Steps

Confirm product categories, one warehouse, four work centers, active BoMs with no packaging product in standard BoM component lines, packaging recipes for active packaged products, and no manufacturing orders, inventory adjustments, stock moves, or journal entries.

## Test-Manufacturing Procedure

Use a separate copy of the database. Create a draft MO using an active custom BoM, add planned packaged output lines, reload packaging recipes, and verify generated raw moves contain packaging once with `component_source = packaging_recipe`.

## Rollback / Uninstall Considerations

Roll back from a database backup before uninstalling if the master data has been used in transactions. Odoo may restrict deletion of records referenced by transactional data.

## Known Source-Data Limitations

See `reports/data_quality_report.md` and `reports/unresolved_records.csv`. Known problematic BOMs are installed inactive. By-product quantities, yield/loss percentages, and several mismatched packaging names require customer confirmation.

## Questions to Send to Legacy

- Confirm all records listed in `unresolved_records.csv`.
- Confirm by-product output quantities and producing operations.
- Confirm whether generic outer packaging should map to pack-specific outer packaging.
- Confirm Woven Bag 25kg vs Woven Bag 50kg for Instant Thobwa 25kg.
- Confirm process losses and yield percentages for each product family.
