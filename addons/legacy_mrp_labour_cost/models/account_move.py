from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    labour_production_id = fields.Many2one(
        "mrp.production",
        string="Labour Manufacturing Order",
        index=True,
        copy=False,
        check_company=True,
        help="Manufacturing Order whose supplementary labour cost this entry represents.",
    )
