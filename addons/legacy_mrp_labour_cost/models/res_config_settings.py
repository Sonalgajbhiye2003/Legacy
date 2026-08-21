from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    manufacturing_labour_journal_id = fields.Many2one(
        related="company_id.manufacturing_labour_journal_id",
        readonly=False,
    )
    manufacturing_labour_debit_account_id = fields.Many2one(
        related="company_id.manufacturing_labour_debit_account_id",
        readonly=False,
    )
    manufacturing_labour_credit_account_id = fields.Many2one(
        related="company_id.manufacturing_labour_credit_account_id",
        readonly=False,
    )
