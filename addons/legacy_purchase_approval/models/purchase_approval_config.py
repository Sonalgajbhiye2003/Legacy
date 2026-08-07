from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LegacyPurchaseApprovalConfig(models.Model):
    _name = "legacy.purchase.approval.config"
    _description = "Purchase Approval Configuration"
    _order = "sequence, id"
    _check_company_auto = True

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(default=True)
    level_1_approver_id = fields.Many2one(
        "res.users",
        string="Level 1 Approver",
        required=True,
        domain="[('share', '=', False), ('company_ids', 'in', company_id)]",
    )
    level_2_approver_id = fields.Many2one(
        "res.users",
        string="Level 2 Approver",
        domain="[('share', '=', False), ('company_ids', 'in', company_id)]",
    )
    level_3_approver_id = fields.Many2one(
        "res.users",
        string="Level 3 Approver",
        domain="[('share', '=', False), ('company_ids', 'in', company_id)]",
    )
    min_amount = fields.Monetary(default=0.0, currency_field="currency_id")
    max_amount = fields.Monetary(
        default=0.0,
        currency_field="currency_id",
        help="Leave at zero for no upper limit.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    apply_to_all_purchase_orders = fields.Boolean(
        string="Apply to All Purchase Orders",
        help="Ignore the configured amount range.",
    )
    sequence = fields.Integer(default=10, help="Lower sequences are selected first.")

    @api.onchange("company_id")
    def _onchange_company_id(self):
        if self.company_id:
            self.currency_id = self.company_id.currency_id

    @api.constrains(
        "level_1_approver_id",
        "level_2_approver_id",
        "level_3_approver_id",
    )
    def _check_approver_levels(self):
        for config in self:
            if config.level_3_approver_id and not config.level_2_approver_id:
                raise ValidationError(
                    _("A Level 2 approver is required when Level 3 is configured.")
                )
            approvers = [
                approver.id
                for approver in (
                    config.level_1_approver_id,
                    config.level_2_approver_id,
                    config.level_3_approver_id,
                )
                if approver
            ]
            if len(approvers) != len(set(approvers)):
                raise ValidationError(
                    _("The same user cannot be assigned to multiple approval levels.")
                )

    @api.constrains("min_amount", "max_amount", "apply_to_all_purchase_orders")
    def _check_amount_range(self):
        for config in self:
            if config.min_amount < 0 or config.max_amount < 0:
                raise ValidationError(_("Approval amounts cannot be negative."))
            if (
                not config.apply_to_all_purchase_orders
                and config.max_amount
                and config.max_amount < config.min_amount
            ):
                raise ValidationError(
                    _("Maximum Amount must be greater than or equal to Minimum Amount.")
                )

    def matches_purchase_order(self, order):
        """Return whether this configuration applies to ``order``."""
        self.ensure_one()
        if self.company_id != order.company_id or not self.active:
            return False
        if self.apply_to_all_purchase_orders:
            return True
        conversion_date = fields.Date.to_date(order.date_order) or fields.Date.context_today(order)
        amount = order.currency_id._convert(
            order.amount_total,
            self.currency_id,
            order.company_id,
            conversion_date,
        )
        if amount < self.min_amount:
            return False
        return not self.max_amount or amount <= self.max_amount
