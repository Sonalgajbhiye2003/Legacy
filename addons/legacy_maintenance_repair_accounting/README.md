# Legacy Maintenance, Repair and Accounting

Production integration for Legacy maintenance, standard Repair Orders, Material Requisitions, inventory valuation, labour costing, build capitalization, and fixed assets when available.

The addon does not create a new application. It extends the existing Maintenance, Repairs, Inventory and Accounting interfaces. Manufacturing Orders, BoMs, Projects, Tasks and Timesheets are outside its workflow.

## Foundation configuration

Configure company-specific accounts, journals, CAPEX/OPEX production locations, labour posting mode and zero-cost policy under Accounting Settings > Maintenance and Repair Accounting.

Automated-valuation material issues use the valuation input account of the selected CAPEX/OPEX production location. Manual-valuation material issues use the configured material journal and inventory account.

## Workflow

1. Raise a Work Centre Maintenance Request and select Repair Existing Machine or Build New Machine.
2. Create the linked standard Repair Order. One request can create only one order.
3. Plan operations and capture labour using timers or reasoned manual entries.
4. Add Repair Parts, create one Material Requisition, and obtain Finance CAPEX/OPEX approval before reservation or consumption.
5. Let Repair own the consumption move. Requisitions and purchases authorize/supply that move; they never create a duplicate issue.
6. Approve labour and post it according to the company mode.
7. Complete Repair to update the equipment component register.
8. For Build orders, run Capitalize Build after all readiness checks pass. The entry debits PPE and credits CWIP, creates/commissions Equipment, and creates a fixed asset when the optional asset bridge is installed.

## Documentation

- [Configuration guide](docs/CONFIGURATION.md)
- [Accounting and posting ownership](docs/ACCOUNTING.md)
- [Security roles](docs/SECURITY.md)
- [User guide](docs/USER_GUIDE.md)
- [Technical architecture and model relationships](docs/ARCHITECTURE.md)
- [Testing and upgrade notes](docs/TESTING_AND_UPGRADE.md)

## Scope guarantees

This solution creates no Manufacturing Order, BoM, Project, Task, or Timesheet. It adds no top-level application. The optional `legacy_maintenance_repair_asset` bridge is the only dependency-boundary addon; the core remains installable without Enterprise Assets.
