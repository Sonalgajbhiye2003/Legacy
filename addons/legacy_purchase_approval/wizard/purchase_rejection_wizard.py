from odoo import fields, models, _
from odoo.exceptions import UserError


class LegacyPurchaseRejectionWizard(models.TransientModel):
    _name = "legacy.purchase.rejection.wizard"
    _description = "Purchase Order Rejection"

    purchase_order_id = fields.Many2one(
        "purchase.order",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    rejection_reason = fields.Text(required=True)

    def action_confirm_rejection(self):
        self.ensure_one()
        reason = (self.rejection_reason or "").strip()
        if not reason:
            raise UserError(_("A rejection reason is required."))
        self.purchase_order_id._apply_rejection(reason)
        return {"type": "ir.actions.act_window_close"}
