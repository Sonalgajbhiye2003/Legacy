from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    quantity_warning_tolerance = fields.Float(default=0.01, digits="Product Unit of Measure")
    quantity_blocking_tolerance = fields.Float(default=0.10, digits="Product Unit of Measure")
    packaging_variance_reason_threshold = fields.Float(default=0.0, digits="Product Unit of Measure")
    byproduct_variance_reason_threshold = fields.Float(default=0.0, digits="Product Unit of Measure")
