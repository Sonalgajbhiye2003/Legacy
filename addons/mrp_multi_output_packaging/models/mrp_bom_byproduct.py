from odoo import fields, models


class MrpBomByproduct(models.Model):
    _inherit = "mrp.bom.byproduct"

    variance_reason_required_above = fields.Float(
        string="Variance Reason Threshold",
        related="company_id.byproduct_variance_reason_threshold",
        readonly=True,
    )
