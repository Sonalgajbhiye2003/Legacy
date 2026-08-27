# Legacy Odoo Modules Inventory

## Repository modules

| Module folder | Module name | Dependencies | Usage |
|---|---|---|---|
| `addons/stock_request` | Material Requisition | `stock`, `purchase_stock`, `mrp`, `analytic` | Material requisition workflow with configurable approval matrix used for stock-based requests before downstream procurement or transfers. |
| `addons/legacy_purchase_approval` | Legacy Purchase Approval | `purchase`, `mail` | Configurable one-to-three-level purchase order approval workflows. |
| `addons/legacy_mrp_master_data` | Legacy MRP Master Data | `mrp_multi_output_packaging`, `purchase_stock`, `mrp_workorder` | Master data setup for Legacy manufacturing (products, warehouses, work centers, BoMs, operations, packaging). |
| `addons/legacy_mrp_labour_cost` | Legacy Manufacturing Labour Cost | `mrp`, `mrp_account`, `account`, `mail` | Capture, posting, reversing, and analysis of manufacturing labour costs. |
| `addons/legacy_maintenance_repair_asset` | Legacy Maintenance Repair Asset Bridge | `account_asset`, `legacy_maintenance_repair_accounting` | Optional bridge to account for capitalization and asset-related maintenance repair cost flows. |
| `addons/legacy_maintenance_repair_accounting` | Legacy Maintenance, Repair and Accounting | `account`, `hr`, `maintenance`, `mrp_maintenance`, `purchase_stock`, `repair`, `stock_account`, `stock_request` | Shared accounting foundation for maintenance/repair operations and cost control. |
| `addons/legacy_ui_icon_fix` | Legacy UI Icon Fix | `base`, `to_base` | Restores/standardizes Apps and Settings home-menu icons. |
| `addons/mrp_multi_output_packaging` | MRP Multi-Output Packaging | `mrp`, `stock`, `product`, `uom`, `mail` | Supports multi-output and packaging-specific manufacturing flows with quantity reconciliation. |
| `third_party_addons/web_chatter_position_cr` | Web Chatter Position | `web`, `mail` | UI-level chatter positioning/customization behavior for user-specific layouts. |
| `third_party_addons/impersonate_login` | Impersonate Login | `web`, `mail` | Provides impersonation utilities for login/support workflows. |

## Notes
- Core custom modules are in `addons/`.
- Third-party reviewed add-ons are in `third_party_addons/`.
- Licensed/private add-ons should remain in `private_addons/` and are ignored from Git.
