# Legacy Odoo 17 Manufacturing

Source repository for Legacy Manufacturers' Odoo 17 manufacturing extensions and user documentation.

## Add-ons

- `addons/mrp_multi_output_packaging` — custom multi-output manufacturing, packaged-output planning, packaging calculations, and reconciliation.
- `addons/legacy_mrp_master_data` — Legacy products, variants, work centres, operations, BoMs, packaging recipes, and quality master data.

## Documentation

- `Legacy_Odoo17_Manufacturing_User_Manual.docx` — validated manufacturing user manual.
- `build_manufacturing_manual.py` and `manual_assets/` — reproducible manual source and screenshots.

## Working agreement

This repository is the source of truth. Make and review changes in a local clone, commit them, and push them before deployment. At the beginning of future work, update the clone with:

```powershell
git pull --ff-only
```

The running development instance loads deployed copies from `C:\Odoo\17\custom_addons`. Repository changes should be validated, committed, and then copied to that deployment path before upgrading the relevant Odoo module.

Never commit Odoo configuration files, database credentials, runtime data, logs, caches, or generated render-check files.
