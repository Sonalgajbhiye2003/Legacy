# MRP Multi-Output Packaging

Odoo 17 Enterprise foundation for planning multiple packaged outputs from a manufacturing order, calculating recipe-driven packaging consumption, consolidating common packaging components, and reconciling packaged equivalents with remaining bulk output.

## Scope

- Standard Odoo or Custom Multi-Output workflow per BoM and MO.
- Integrated Production and Packaging and Multi-Variant Packaging process types.
- Variant-level packaged-product configuration.
- Date-effective, versioned packaging recipes with chatter.
- Immutable recipe snapshots at MO confirmation.
- Finished Output Plan and packaging-consumption breakdown on the standard MO.
- Packaging stock moves consolidated by product, UoM, operation, source location, and company.
- Soya Chunk planned/actual bulk reconciliation and company tolerances.
- Completion blocking for invalid custom quantities, missing recipes/net content/lots, and reconciliation warnings.
- Company-safe security groups and record rules.

## Simplified operator workflow

1. Create the Manufacturing Order and select the BoM.
2. Review the automatically selected bulk and packaged products.
3. Select **Confirm**.
4. Record produced quantities and lots, then complete the order.

Confirmation automatically selects the configured recipes, calculates packaging
requirements, creates packaging component moves, and freezes recipe snapshots.
Operators do not need to reload recipes or recalculate outputs manually.
The BoM supplies the default packaged product and calculates its planned quantity
from the Manufacturing Order's bulk quantity and the product's net content.

Technical packaging calculations and automatically calculated variances are shown only to
Multi-Output Manufacturing Supervisors under **Packaging Review**.

## Explicitly outside milestone 1

Custom finished-output valuation, accounting allocation, Soya Oil packaging completion, custom unbuild valuation, dashboards, and advanced reporting are not implemented. Genuine by-products remain on Odoo's standard BoM by-product and finished-move path.

## Installation

The initial dependency list is deliberately limited to `mrp`, `stock`, `product`, `uom`, and `mail`. Install and test only on a development copy before deployment.
