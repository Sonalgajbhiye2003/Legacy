from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


LABOUR_TYPES = [
    ("production", "Production"),
    ("packaging", "Packaging"),
    ("loading", "Loading"),
    ("handling", "Handling"),
    ("other", "Other"),
]


class MrpLabourCostPreset(models.Model):
    _name = "mrp.labour.cost.preset"
    _description = "Manufacturing Labour Preset"
    _order = "name, id"
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    workcenter_id = fields.Many2one(
        "mrp.workcenter", string="Default Work Center", required=True, check_company=True
    )
    labour_type = fields.Selection(LABOUR_TYPES, required=True, default="production")
    description = fields.Char(string="Default Description")
    labour_count = fields.Integer(string="Default No. of Labour", required=True, default=1)
    hours_per_labour = fields.Float(
        string="Default Hours per Labour", required=True, digits=(16, 2), default=0.0
    )
    cost_per_hour = fields.Monetary(
        string="Default Cost per Hour",
        required=True,
        currency_field="currency_id",
        default=0.0,
    )
    note = fields.Text()

    _sql_constraints = [
        (
            "name_company_unique",
            "UNIQUE(name, company_id)",
            "A labour preset name must be unique per company.",
        ),
        ("labour_count_positive", "CHECK(labour_count > 0)", "Labour count must be positive."),
        ("hours_non_negative", "CHECK(hours_per_labour >= 0)", "Hours cannot be negative."),
        ("rate_non_negative", "CHECK(cost_per_hour >= 0)", "Cost per hour cannot be negative."),
    ]

    @api.constrains("labour_count", "hours_per_labour", "cost_per_hour")
    def _check_numeric_values(self):
        for preset in self:
            if preset.labour_count <= 0:
                raise ValidationError(_("Labour count must be greater than zero."))
            if preset.hours_per_labour < 0 or preset.cost_per_hour < 0:
                raise ValidationError(_("Labour hours and cost per hour cannot be negative."))
