from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    legacy_commissioning_state = fields.Selection(
        [("under_construction", "Under Construction"), ("in_service", "In Service")],
        string="Commissioning Status",
        default="in_service",
        required=True,
        tracking=True,
    )
    legacy_commissioning_date = fields.Date(copy=False, tracking=True)
    legacy_capitalized_cost = fields.Monetary(currency_field="legacy_currency_id", copy=False, tracking=True)
    legacy_currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    legacy_build_order_id = fields.Many2one("repair.order", string="Build Order", copy=False, readonly=True, check_company=True, ondelete="restrict")


class AccountMove(models.Model):
    _inherit = "account.move"

    legacy_capitalization_repair_id = fields.Many2one(
        "repair.order", string="Capitalized Build Order", index=True, copy=False, check_company=True, ondelete="restrict"
    )

    _sql_constraints = [
        ("legacy_capitalization_repair_unique", "unique(legacy_capitalization_repair_id)", "A Build Order can have only one capitalization entry."),
    ]


class RepairOrder(models.Model):
    _inherit = "repair.order"

    legacy_capitalization_move_id = fields.Many2one(
        "account.move", string="Capitalization Entry", copy=False, readonly=True, check_company=True, ondelete="restrict"
    )
    legacy_capitalization_reversal_move_ids = fields.Many2many(
        "account.move", "legacy_repair_capitalization_reversal_rel", "repair_order_id", "move_id", string="Capitalization Reversals", copy=False, readonly=True
    )
    legacy_commissioning_date = fields.Date(copy=False, tracking=True)

    def _legacy_capex_lines(self):
        self.ensure_one()
        material_lines = self.legacy_material_request_ids.stock_request_ids.filtered(
            lambda line: line.legacy_expense_type == "capex" and line.legacy_fulfillment_owner == "repair"
        )
        labour_lines = self.legacy_labour_ids.filtered(lambda line: line.expense_type == "capex")
        return material_lines, labour_lines

    def _legacy_cwip_amount(self):
        self.ensure_one()
        account = self.company_id._legacy_validate_account(self.company_id.legacy_cwip_account_id, _("CWIP Account"))
        moves = self.legacy_journal_entry_ids.filtered(lambda move: move.state == "posted" and move.legacy_posting_type in ("material", "material_return", "labour"))
        return sum(moves.line_ids.filtered(lambda line: line.account_id == account).mapped("balance"))

    def _legacy_check_build_readiness(self, commissioning_date=False):
        self.ensure_one()
        if self.legacy_order_type != "build":
            raise UserError(_("Only Build New Machine orders can be capitalized."))
        if not self.legacy_maintenance_request_id or self.legacy_maintenance_request_id.legacy_work_type != "build":
            raise ValidationError(_("A Build Maintenance Request is required."))
        if not self.legacy_target_workcenter_id:
            raise ValidationError(_("Target Work Centre is required."))
        if not commissioning_date:
            raise ValidationError(_("Commissioning Date is required."))
        incomplete = self.legacy_operation_ids.filtered(lambda operation: operation.state != "done")
        if incomplete:
            raise ValidationError(_("Complete every Build operation before capitalization."))
        unapproved_labour = self.legacy_labour_ids.filtered(lambda line: line.approval_state != "approved")
        if unapproved_labour:
            raise ValidationError(_("Every labour entry must be approved before capitalization."))
        if self.company_id.legacy_labour_posting_mode == "post_approved" and self.legacy_labour_ids.filtered(lambda line: line.accounting_status != "posted"):
            raise ValidationError(_("Approved labour must be posted before capitalization."))
        material_lines, labour_lines = self._legacy_capex_lines()
        if material_lines.filtered(lambda line: line.legacy_finance_approval_state != "approved"):
            raise ValidationError(_("Every CAPEX material line must be Finance approved."))
        if material_lines.filtered(lambda line: not line.legacy_repair_move_id or line.legacy_repair_move_id.state != "done"):
            raise ValidationError(_("All CAPEX materials must be consumed before capitalization."))
        if material_lines.filtered(lambda line: line.legacy_accounting_status != "posted"):
            raise ValidationError(_("All CAPEX material accounting must be posted before capitalization."))
        if material_lines.filtered(lambda line: line.legacy_zero_cost_exception_value and not line.legacy_zero_cost_approved_by_id):
            raise ValidationError(_("Resolve all zero-cost exceptions before capitalization."))
        expected = sum(material_lines.mapped("legacy_posted_value")) + sum(labour_lines.mapped("labour_cost"))
        cwip = self._legacy_cwip_amount()
        if float_compare(expected, cwip, precision_rounding=self.currency_id.rounding):
            raise ValidationError(_("CWIP mismatch: attributed CAPEX is %(expected).2f but the posted CWIP balance is %(actual).2f.", expected=expected, actual=cwip))
        if float_is_zero(expected, precision_rounding=self.currency_id.rounding):
            raise ValidationError(_("There is no posted CAPEX cost to capitalize."))
        return expected

    def action_open_legacy_capitalization(self):
        self.ensure_one()
        if not self.env.user.has_group("legacy_maintenance_repair_accounting.group_finance_maintenance_approver"):
            raise AccessError(_("Only Finance can capitalize a Build Order."))
        if self.legacy_capitalization_move_id:
            return {"type": "ir.actions.act_window", "name": _("Capitalization Entry"), "res_model": "account.move", "view_mode": "form", "res_id": self.legacy_capitalization_move_id.id}
        return {
            "type": "ir.actions.act_window",
            "name": _("Capitalize Build"),
            "res_model": "legacy.build.capitalization.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_repair_order_id": self.id, "default_accounting_date": fields.Date.context_today(self)},
        }

    def action_reverse_legacy_capitalization(self):
        self.ensure_one()
        move = self.legacy_capitalization_move_id
        if not move or move.state != "posted":
            raise UserError(_("There is no posted capitalization entry to reverse."))
        reversal = move._reverse_moves([{"date": fields.Date.context_today(self), "ref": _("Reversal of %(ref)s", ref=move.ref)}], cancel=False)
        self.write({"legacy_capitalization_status": "reversed", "legacy_capitalization_reversal_move_ids": [(4, item.id) for item in reversal]})
        if self.legacy_equipment_id:
            self.legacy_equipment_id.write({"legacy_commissioning_state": "under_construction", "legacy_capitalized_cost": 0.0})
        return reversal

    def _legacy_create_or_link_asset(self, ppe_line):
        """Optional asset bridge extension point. Core accounting must work without Assets."""
        return False
