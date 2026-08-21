from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class MrpLabourCostReversalWizard(models.TransientModel):
    _name = "mrp.labour.cost.reversal.wizard"
    _description = "Reverse Manufacturing Labour Cost"
    _check_company_auto = True

    production_id = fields.Many2one(
        "mrp.production", string="Manufacturing Order", required=True, readonly=True
    )
    company_id = fields.Many2one(
        related="production_id.company_id", required=True, readonly=True
    )
    move_id = fields.Many2one(
        "account.move",
        string="Labour Journal Entry",
        required=True,
        check_company=True,
        domain="[('labour_production_id', '=', production_id), ('state', '=', 'posted'), ('reversal_move_id', '=', False)]",
    )
    date = fields.Date(string="Reversal Date", required=True, default=fields.Date.context_today)
    reason = fields.Char(required=True, default="Manufacturing labour cost correction")

    def action_reverse_labour_cost(self):
        self.ensure_one()
        if not self.env.user.has_group("account.group_account_manager"):
            raise AccessError(_("Only an Accounting Manager can reverse labour costs."))
        move = self.move_id
        if move.labour_production_id != self.production_id or move.state != "posted":
            raise UserError(_("Select a posted labour journal entry for this Manufacturing Order."))
        lines = self.production_id.labour_cost_line_ids.filtered(
            lambda line: line.posting_state == "posted" and line.account_move_id == move
        )
        if not lines:
            raise UserError(_("This journal entry has no posted labour lines to reverse."))
        if move.reversal_move_id:
            raise UserError(_("This labour journal entry has already been reversed."))
        reverse_move = move.with_company(self.company_id)._reverse_moves(
            [
                {
                    "date": self.date,
                    "journal_id": move.journal_id.id,
                    "ref": _("Reversal of %(entry)s: %(reason)s", entry=move.name, reason=self.reason),
                    "labour_production_id": self.production_id.id,
                }
            ],
            cancel=True,
        )
        lines._accounting_write(
            {"posting_state": "reversed", "reversal_move_id": reverse_move.id}
        )
        self.production_id.message_post(
            body=_(
                "Labour cost journal entry %(entry)s was reversed through %(reversal)s.",
                entry=move.display_name,
                reversal=reverse_move.display_name,
            ),
            subtype_xmlid="mail.mt_note",
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Labour Cost Reversal"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": reverse_move.id,
        }
