# Legacy Purchase Approval

Configurable one-to-three-level purchase order approval for Odoo 17.

Purchase Managers maintain company-specific configurations under **Purchase >
Configuration > Purchase Approval Configuration**. Configurations are evaluated
by sequence and amount range. Approvers are copied to the Purchase Order when
approval is requested, preserving an auditable snapshot of the workflow.

Approval requests and final results are queued through standard Odoo mail
templates and recorded in the Purchase Order chatter. Rejections require the
modal rejection wizard. A rejected request can only be reset by a Purchase
Manager.
