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

## Why Some Screens Show Two Lines

Odoo's `Manufacturing > Configuration > Operations` action filters operations to active BOMs. Only two production families currently have active validated BOMs:

- TSP
- Instant Porridge

Instant Thobwa and Corn Puffs operations are present, but their BOMs remain inactive because the source BOM workbook contains known unresolved quantity/formula issues for those sheets. This is intentional: activating them would make unvalidated BOMs usable in production.

## Current Decision

Keep all four work centers active. Keep unresolved Instant Thobwa and Corn Puffs BOMs inactive until Legacy confirms the missing or ambiguous quantities.
