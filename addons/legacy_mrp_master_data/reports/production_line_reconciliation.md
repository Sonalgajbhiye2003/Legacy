# Production Line Reconciliation

Run date: 2026-08-02

## Source Documents Used

- `C:\Users\SONAL\OneDrive\Desktop\Legacy Group Docs\June 26 stock sheet.xlsx`
- `C:\Users\SONAL\OneDrive\Desktop\Legacy Group Docs\Legacy products  BOM-July 26.xlsx`
- `C:\Users\SONAL\OneDrive\Desktop\Legacy Group Docs\OPS010-Process Flow Diagrams.xlsx`

## Source Evidence

The process-flow workbook contains four manufacturing process sheets:

- `TSP Flow diagram`
- `Thobwa Flow diagram`
- `Instant porridge Flow diagram`
- `Corn-puffs`

The BOM workbook also contains product-family sheets for the same four lines:

- TSP: `TSP 90g`, `TSP 700g x 10`, `TSP 700g x5`, `TSP 3Kg`, `TSP 3Kg woven`, `TSP 8Kg`
- Instant Thobwa: `Instant thobwa`, `Instant thobwa-25Kg`
- Instant Porridge: `Instant porridge 500g`, `Instant porridge 1Kg`, `Instant porridge 10Kg`, `Instant porridge 50Kg`, `Instant porridge boxed`
- Corn Puffs: `16g Corn puffs`, `Corn sticks`, `60g x30 Corn puffs`

## Odoo Work Centers Created

The addon creates four active line-level Odoo work centers:

- `WC-TSP-01 TSP Production Line`
- `WC-THO-01 Instant Thobwa Production Line`
- `WC-POR-01 Instant Porridge Production Line`
- `WC-PUF-01 Corn Puffs Production Line`

These are visible from `Manufacturing > Configuration > Work Centers`.

## Active Production Lines

Odoo's active BOM list now shows one process BOM per bulk product family:

- `LEGACY-SOYA-CHUNKS-SINGLE-PROCESS`
- `LEGACY-INSTANT-THOBWA-SINGLE-PROCESS`
- `LEGACY-CORN-PUFFS-SINGLE-PROCESS`
- the existing validated Instant Porridge BOM

TSP, Instant Thobwa, and Corn Puffs pack sizes are product variants with packaging recipes. The old pack-specific manufacturing BOMs are archived, so a pack size no longer duplicates the underlying process formulation.

## Current Decision

Keep all four work centers active. Use the consolidated 1 kg process BOMs for manufacturing and the variant recipe layer for packaging. Zed Crunch/Corn Sticks remains excluded because its product identity, net content, tomato formulation, and packaging mappings still require confirmation.
