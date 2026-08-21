from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StockRequestApprovalConfig(models.Model):
    _name = "stock.request.approval.config"
    _description = "Stock Request Approval Configuration"
    _order = "sequence, id"
    _check_company_auto = True

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    requester_id = fields.Many2one(
        "res.users",
        string="Requester",
        domain="[('share', '=', False), ('company_ids', 'in', company_id)]",
        help="Leave blank to apply this matrix to every requester in the company.",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
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

    @api.constrains(
        "level_1_approver_id", "level_2_approver_id", "level_3_approver_id"
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

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_approver_group()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {
            "level_1_approver_id",
            "level_2_approver_id",
            "level_3_approver_id",
        }.intersection(vals):
            self._ensure_approver_group()
        return result

    def _ensure_approver_group(self):
        group = self.env.ref("stock_request.group_stock_request_approver")
        approvers = (
            self.mapped("level_1_approver_id")
            | self.mapped("level_2_approver_id")
            | self.mapped("level_3_approver_id")
        )
        approvers.filtered(lambda user: group not in user.groups_id).write(
            {"groups_id": [(4, group.id)]}
        )
