# Accounting Configuration and Posting Ownership

| Event | Posting owner | Debit | Credit | Duplicate protection |
|---|---|---|---|---|
| Automated material issue | Standard Stock Accounting | CAPEX location valuation / OPEX expense | Stock valuation | Links the standard SVL entry; no custom entry |
| Manual material issue | This integration | CWIP / Repair Expense | Inventory | One batched requisition entry |
| Material return | Stock Accounting or this integration, matching issue mode | Inventory | Original debit account | Original move/value link and one return entry |
| Approved labour | Reporting only or this integration | CWIP / Repair Expense | Labour Clearing | Only unposted approved lines are batched |
| Build capitalization | This integration | PPE | CWIP | Unique Build Order constraint and row lock |
| Fixed asset | Standard Assets workflow | No new acquisition entry | No new acquisition entry | Asset uses the PPE debit journal item |

The Accounting Reconciliation report compares Repair material cost, stock valuation, journal value, approved/posted labour, CAPEX, CWIP, and capitalization. The exception action highlights approval, posting, CWIP, and uncapitalized-Build gaps.
