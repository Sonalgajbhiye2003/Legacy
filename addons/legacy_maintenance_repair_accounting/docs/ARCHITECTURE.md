# Technical Architecture and Model Relationships

The core addon extends standard `maintenance.request`, `repair.order`, `stock.request.order`, `stock.request`, `stock.move`, `stock.valuation.layer`, `purchase.order.line`, `account.move`, `account.move.line`, `maintenance.equipment`, `hr.employee`, and `mrp.workcenter`.

It owns three operational models: `legacy.repair.operation`, `legacy.repair.labour`, and `maintenance.equipment.component` with immutable component events. `legacy.repair.cost.reconciliation` is a read-only SQL reporting view. `legacy.build.capitalization.wizard` controls final capitalization.

Traceability paths:

- Material: Maintenance Request → Repair/Build Order → Operation → Repair Part move → Material Requisition line → Purchase/receipt when needed → consumption move → SVL → journal entry → Equipment Component.
- Labour: Maintenance Request → Repair/Build Order → Operation → Labour Entry → approval → journal entry.
- Build: Maintenance Request → Build Order → CAPEX/CWIP → capitalization entry → Fixed Asset (optional bridge) → Equipment → Work Centre.

Repair is the sole owner of material consumption. Standard Stock Accounting remains the sole automated-valuation owner. The asset bridge depends on Enterprise Assets and never creates a second acquisition entry.
