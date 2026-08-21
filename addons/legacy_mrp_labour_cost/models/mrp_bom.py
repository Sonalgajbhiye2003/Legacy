from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .labour_preset import LABOUR_TYPES


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    labour_preset_line_ids = fields.One2many(
        "mrp.bom.labour.cost", "bom_id", string="Labour Presets", copy=True
    )


class MrpBomLabourCost(models.Model):
    _name = "mrp.bom.labour.cost"
    _description = "Bill of Materials Labour Cost"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    bom_id = fields.Many2one(
        "mrp.bom", required=True, index=True, ondelete="cascade", check_company=True
    )
    company_id = fields.Many2one(
        "res.company", related="bom_id.company_id", store=True, readonly=True, index=True
    )
    currency_id = fields.Many2one(
        "res.currency", related="bom_id.company_id.currency_id", readonly=True
    )
    labour_preset_id = fields.Many2one(
        "mrp.labour.cost.preset", string="Labour Preset", required=True, index=True
    )
    operation_id = fields.Many2one(
        "mrp.routing.workcenter", string="Operation", index=True, ondelete="set null"
    )
    workcenter_id = fields.Many2one(
        "mrp.workcenter", string="Work Center", required=True, index=True
    )
    labour_type = fields.Selection(LABOUR_TYPES, required=True, default="production")
    description = fields.Char()
    labour_count = fields.Integer(string="No. of Labour", required=True, default=1)
    hours_per_labour = fields.Float(
        string="Hours per Labour", required=True, digits=(16, 2), default=0.0
    )
    cost_per_hour = fields.Monetary(
        string="Cost per Hour", required=True, currency_field="currency_id", default=0.0
    )

    _sql_constraints = [
        ("labour_count_positive", "CHECK(labour_count > 0)", "Labour count must be positive."),
        ("hours_non_negative", "CHECK(hours_per_labour >= 0)", "Hours cannot be negative."),
        ("rate_non_negative", "CHECK(cost_per_hour >= 0)", "Cost per hour cannot be negative."),
    ]

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            preset = self.env["mrp.labour.cost.preset"].browse(
                values.get("labour_preset_id")
            )
            if preset:
                values.setdefault("workcenter_id", preset.workcenter_id.id)
                values.setdefault("labour_type", preset.labour_type)
                values.setdefault("description", preset.description or preset.name)
                values.setdefault("labour_count", preset.labour_count)
                values.setdefault("hours_per_labour", preset.hours_per_labour)
                values.setdefault("cost_per_hour", preset.cost_per_hour)
            operation = self.env["mrp.routing.workcenter"].browse(
                values.get("operation_id")
            )
            if operation:
                values["workcenter_id"] = operation.workcenter_id.id
        return super().create(values_list)

    @api.onchange("labour_preset_id")
    def _onchange_labour_preset_id(self):
        if not self.labour_preset_id:
            return
        preset = self.labour_preset_id
        self.workcenter_id = preset.workcenter_id
        self.labour_type = preset.labour_type
        self.description = preset.description or preset.name
        self.labour_count = preset.labour_count
        self.hours_per_labour = preset.hours_per_labour
        self.cost_per_hour = preset.cost_per_hour

    @api.onchange("operation_id")
    def _onchange_operation_id(self):
        if self.operation_id:
            self.workcenter_id = self.operation_id.workcenter_id

    @api.constrains(
        "bom_id",
        "labour_preset_id",
        "operation_id",
        "workcenter_id",
        "labour_count",
        "hours_per_labour",
        "cost_per_hour",
    )
    def _check_configuration(self):
        for line in self:
            company = line.bom_id.company_id
            if company and line.labour_preset_id.company_id != company:
                raise ValidationError(_("The labour preset must belong to the BoM company."))
            if line.workcenter_id.company_id and company and line.workcenter_id.company_id != company:
                raise ValidationError(_("The Work Center must belong to the BoM company."))
            if line.operation_id:
                if line.operation_id.bom_id != line.bom_id:
                    raise ValidationError(_("The Operation must belong to this BoM."))
                if line.operation_id.workcenter_id != line.workcenter_id:
                    raise ValidationError(_("The Work Center must match the selected Operation."))
            if line.labour_count <= 0:
                raise ValidationError(_("Labour count must be greater than zero."))
            if line.hours_per_labour < 0 or line.cost_per_hour < 0:
                raise ValidationError(_("Labour hours and cost per hour cannot be negative."))

    def _prepare_production_labour_values(self, production):
        self.ensure_one()
        return {
            "production_id": production.id,
            "bom_labour_line_id": self.id,
            "labour_preset_id": self.labour_preset_id.id,
            "workcenter_id": self.workcenter_id.id,
            "operation_id": self.operation_id.id,
            "labour_type": self.labour_type,
            "description": self.description or self.labour_preset_id.name,
            "labour_count": self.labour_count,
            "hours_per_labour": self.hours_per_labour,
            "cost_per_hour": self.cost_per_hour,
        }
