from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


PROTECTED_POSTED_FIELDS = {
    "production_id",
    "workcenter_id",
    "operation_id",
    "workorder_id",
    "bom_labour_line_id",
    "labour_preset_id",
    "labour_type",
    "labour_count",
    "hours_per_labour",
    "cost_per_hour",
}


class MrpProductionLabourCost(models.Model):
    _name = "mrp.production.labour.cost"
    _description = "Manufacturing Order Labour Cost"
    _order = "production_date desc, production_id, id"
    _check_company_auto = True

    production_id = fields.Many2one(
        "mrp.production",
        string="Manufacturing Order",
        required=True,
        index=True,
        ondelete="cascade",
        check_company=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="production_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    workcenter_id = fields.Many2one(
        "mrp.workcenter",
        string="Work Center",
        required=True,
        index=True,
        check_company=True,
    )
    operation_id = fields.Many2one(
        "mrp.routing.workcenter",
        string="Operation",
        index=True,
        check_company=True,
    )
    workorder_id = fields.Many2one(
        "mrp.workorder",
        string="Work Order",
        index=True,
        check_company=True,
    )
    bom_labour_line_id = fields.Many2one(
        "mrp.bom.labour.cost",
        string="BoM Labour Source",
        readonly=True,
        copy=False,
        index=True,
        ondelete="set null",
    )
    labour_preset_id = fields.Many2one(
        "mrp.labour.cost.preset",
        string="Labour Preset",
        readonly=True,
        copy=False,
        index=True,
        ondelete="set null",
    )
    description = fields.Char(string="Labour Description")
    labour_type = fields.Selection(
        [
            ("production", "Production"),
            ("packaging", "Packaging"),
            ("loading", "Loading"),
            ("handling", "Handling"),
            ("other", "Other"),
        ],
        required=True,
        default="production",
        index=True,
    )
    labour_count = fields.Integer(string="No. of Labour", required=True, default=1)
    hours_per_labour = fields.Float(
        string="Hours per Labour", required=True, digits=(16, 2), default=0.0
    )
    cost_per_hour = fields.Monetary(
        string="Cost per Hour", required=True, currency_field="currency_id", default=0.0
    )
    total_hours = fields.Float(
        string="Total Labour Hours",
        compute="_compute_totals",
        store=True,
        digits=(16, 2),
    )
    total_cost = fields.Monetary(
        string="Total Labour Cost",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )
    note = fields.Text()
    posting_state = fields.Selection(
        [("draft", "Unposted"), ("posted", "Posted"), ("reversed", "Reversed")],
        required=True,
        default="draft",
        copy=False,
        index=True,
        readonly=True,
    )
    account_move_id = fields.Many2one(
        "account.move",
        string="Journal Entry",
        readonly=True,
        copy=False,
        check_company=True,
        ondelete="restrict",
        index=True,
    )
    posting_date = fields.Date(readonly=True, copy=False, index=True)
    posted_by_id = fields.Many2one(
        "res.users", string="Posted By", readonly=True, copy=False
    )
    reversal_move_id = fields.Many2one(
        "account.move",
        string="Reversal Entry",
        readonly=True,
        copy=False,
        check_company=True,
        ondelete="restrict",
    )

    production_date = fields.Datetime(
        related="production_id.date_start",
        string="Manufacturing Date",
        store=True,
        readonly=True,
        index=True,
    )
    product_id = fields.Many2one(
        related="production_id.product_id",
        string="Product",
        store=True,
        readonly=True,
        index=True,
    )
    produced_quantity = fields.Float(
        string="Actual Quantity Produced", compute="_compute_production_metrics"
    )
    product_uom_id = fields.Many2one(
        related="production_id.product_uom_id", string="Unit of Measure", readonly=True
    )
    labour_cost_per_unit = fields.Monetary(
        string="Labour Cost per Manufactured Unit",
        compute="_compute_production_metrics",
        currency_field="currency_id",
    )

    _sql_constraints = [
        (
            "labour_count_positive",
            "CHECK(labour_count > 0)",
            "The number of labourers must be greater than zero.",
        ),
        (
            "hours_non_negative",
            "CHECK(hours_per_labour >= 0)",
            "Hours per labourer cannot be negative.",
        ),
        (
            "rate_non_negative",
            "CHECK(cost_per_hour >= 0)",
            "Cost per hour cannot be negative.",
        ),
        (
            "posting_link_consistency",
            "CHECK((posting_state = 'draft' AND account_move_id IS NULL AND reversal_move_id IS NULL) "
            "OR (posting_state = 'posted' AND account_move_id IS NOT NULL AND reversal_move_id IS NULL) "
            "OR (posting_state = 'reversed' AND account_move_id IS NOT NULL AND reversal_move_id IS NOT NULL))",
            "Labour posting status and journal links are inconsistent.",
        ),
        (
            "production_bom_labour_unique",
            "UNIQUE(production_id, bom_labour_line_id)",
            "A BoM labour preset can only be loaded once per Manufacturing Order.",
        ),
    ]

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            self._validate_numeric_values(values)
        return super().create(values_list)

    def _validate_numeric_values(self, values):
        """Reject invalid values before PostgreSQL checks the SQL constraints."""
        self.ensure_one() if self else None
        labour_count = values.get("labour_count", self.labour_count if self else 1)
        hours = values.get("hours_per_labour", self.hours_per_labour if self else 0.0)
        rate = values.get("cost_per_hour", self.cost_per_hour if self else 0.0)
        if labour_count <= 0:
            raise ValidationError(_("The number of labourers must be greater than zero."))
        if hours < 0:
            raise ValidationError(_("Hours per labourer cannot be negative."))
        if rate < 0:
            raise ValidationError(_("Cost per hour cannot be negative."))

    @api.depends("labour_count", "hours_per_labour", "cost_per_hour")
    def _compute_totals(self):
        for line in self:
            line.total_hours = line.labour_count * line.hours_per_labour
            line.total_cost = line.total_hours * line.cost_per_hour

    @api.depends(
        "total_cost",
        "production_id.move_finished_ids.state",
        "production_id.move_finished_ids.picked",
        "production_id.move_finished_ids.quantity",
    )
    def _compute_production_metrics(self):
        for line in self:
            produced = line.production_id.qty_produced
            line.produced_quantity = produced
            line.labour_cost_per_unit = line.total_cost / produced if produced else 0.0

    @api.onchange("workorder_id")
    def _onchange_workorder_id(self):
        if self.workorder_id:
            self.workcenter_id = self.workorder_id.workcenter_id
            self.operation_id = self.workorder_id.operation_id

    @api.onchange("operation_id")
    def _onchange_operation_id(self):
        if self.operation_id:
            self.workcenter_id = self.operation_id.workcenter_id

    @api.constrains("production_id", "workcenter_id", "operation_id", "workorder_id")
    def _check_mrp_consistency(self):
        for line in self:
            production = line.production_id
            if line.workcenter_id.company_id and line.workcenter_id.company_id != production.company_id:
                raise ValidationError(
                    _("The Work Center must belong to the Manufacturing Order company.")
                )
            if line.operation_id:
                if not production.bom_id or line.operation_id.bom_id != production.bom_id:
                    raise ValidationError(
                        _("The Operation must belong to the Manufacturing Order BoM.")
                    )
                if line.operation_id.workcenter_id != line.workcenter_id:
                    raise ValidationError(
                        _("The Work Center must match the selected Operation.")
                    )
            if line.workorder_id:
                if line.workorder_id.production_id != production:
                    raise ValidationError(
                        _("The Work Order must belong to the same Manufacturing Order.")
                    )
                if line.workorder_id.workcenter_id != line.workcenter_id:
                    raise ValidationError(
                        _("The Work Center must match the selected Work Order.")
                    )
                if line.operation_id and line.workorder_id.operation_id != line.operation_id:
                    raise ValidationError(
                        _("The Operation must match the selected Work Order.")
                    )

    @api.constrains("labour_count", "hours_per_labour", "cost_per_hour")
    def _check_labour_values(self):
        for line in self:
            if line.labour_count <= 0:
                raise ValidationError(_("The number of labourers must be greater than zero."))
            if line.hours_per_labour < 0:
                raise ValidationError(_("Hours per labourer cannot be negative."))
            if line.cost_per_hour < 0:
                raise ValidationError(_("Cost per hour cannot be negative."))

    def write(self, values):
        for line in self:
            line._validate_numeric_values(values)
        if (
            PROTECTED_POSTED_FIELDS.intersection(values)
            and not self.env.context.get("labour_accounting_internal")
            and self.filtered(lambda line: line.posting_state != "draft")
        ):
            raise AccessError(
                _("Posted or reversed labour lines cannot be changed. Reverse the journal entry and add a corrected line.")
            )
        protected_status_fields = {
            "posting_state",
            "account_move_id",
            "posting_date",
            "posted_by_id",
            "reversal_move_id",
        }
        if protected_status_fields.intersection(values) and not self.env.context.get(
            "labour_accounting_internal"
        ):
            raise AccessError(_("Labour posting fields can only be changed by accounting actions."))
        return super().write(values)

    def unlink(self):
        if self.filtered(lambda line: line.posting_state != "draft"):
            raise UserError(_("Posted or reversed labour lines cannot be deleted."))
        return super().unlink()

    def _accounting_write(self, values):
        return self.with_context(labour_accounting_internal=True).write(values)
