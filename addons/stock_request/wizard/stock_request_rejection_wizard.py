from odoo import _, fields, models
from odoo.exceptions import UserError


class StockRequestRejectionWizard(models.TransientModel):
    _name = "stock.request.rejection.wizard"
    _description = "Stock Request Rejection"

    stock_request_id = fields.Many2one(
        "stock.request", readonly=True, ondelete="cascade"
    )
    stock_request_order_id = fields.Many2one(
        "stock.request.order",
        string="Material Requisition",
        readonly=True,
        ondelete="cascade",
    )
    rejection_reason = fields.Text(required=True)

    def action_confirm_rejection(self):
        self.ensure_one()
        reason = (self.rejection_reason or "").strip()
        if not reason:
            raise UserError(_("A rejection reason is required."))
        request = self.stock_request_order_id or self.stock_request_id
        if not request:
            raise UserError(_("No request was selected."))
        request._apply_rejection(reason)
        return {"type": "ir.actions.act_window_close"}
