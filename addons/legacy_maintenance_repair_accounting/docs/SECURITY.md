# Security Role Guide

| Role | Main responsibility |
|---|---|
| Maintenance User | Raise and follow Maintenance Requests |
| Repair Supervisor | Manage Repair/Build Orders, operations, and components |
| Labour User | Capture labour; cannot see or change protected rates |
| Labour Approver | Approve/reject labour entries |
| Material Requisition Approver | Approve the operational requisition |
| Stores User | Reserve, receive, issue, and return stock after approvals |
| Maintenance CAPEX/OPEX Approver | Approve classifications and post material/labour accounting |
| Asset Capitalization User | Capitalize Builds and reverse capitalization |
| Administrator | Configure and administer the integration |

Server-side checks enforce approvals even when buttons are called through RPC. Company record rules protect custom operational and reconciliation records. Posted journal entries use standard Odoo accounting protections.
