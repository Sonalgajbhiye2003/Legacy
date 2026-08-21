from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_is_zero

from .common import ACCOUNTING_STATUS_SELECTION


class AccountMove(models.Model):
    _inherit = "account.move"

    legacy_material_request_id = fields.Many2one("stock.request.order", string="Material Requisition", index=True, copy=False, ondelete="restrict", check_company=True)
    legacy_stock_request_line_id = fields.Many2one("stock.request", string="Material Requisition Line", index=True, copy=False, ondelete="restrict", check_company=True)
    legacy_posting_type = fields.Selection(
        [("material", "Manual Material Consumption"), ("material_return", "Manual Material Return"), ("labour", "Maintenance Labour"), ("capitalization", "Build Capitalization")],
        index=True,
        copy=False,
    )


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    legacy_stock_request_line_id = fields.Many2one("stock.request", string="Material Requisition Line", index=True, ondelete="restrict", check_company=True)
    legacy_labour_id = fields.Many2one("legacy.repair.labour", string="Labour Entry", index=True, ondelete="restrict", check_company=True)
    legacy_equipment_id = fields.Many2one("maintenance.equipment", string="Equipment", index=True, check_company=True)
    legacy_workcenter_id = fields.Many2one("mrp.workcenter", string="Work Centre", check_company=True)


class StockValuationLayer(models.Model):
    _inherit = "stock.valuation.layer"

    legacy_stock_request_line_id = fields.Many2one(related="stock_move_id.legacy_stock_request_line_id", store=True, index=True)
    legacy_repair_order_id = fields.Many2one(related="stock_move_id.repair_id", store=True, index=True)
    legacy_equipment_id = fields.Many2one(related="stock_move_id.legacy_equipment_id", store=True, index=True)


class StockRequest(models.Model):
    _inherit = "stock.request"

    legacy_accounting_status = fields.Selection(
        ACCOUNTING_STATUS_SELECTION,
        string="Accounting Status",
        required=True,
        default="not_posted",
        tracking=True,
        copy=False,
    )
    legacy_zero_cost_exception_value = fields.Monetary(currency_field="currency_id", copy=False)
    legacy_zero_cost_exception_reason = fields.Text(copy=False)
    legacy_zero_cost_approved_by_id = fields.Many2one("res.users", copy=False, readonly=True)
    legacy_zero_cost_approved_date = fields.Datetime(copy=False, readonly=True)
    legacy_return_move_id = fields.Many2one("stock.move", string="Return Move", copy=False, readonly=True, check_company=True, ondelete="restrict")

    def action_approve_zero_cost_exception(self):
        if not self.env.user.has_group("legacy_maintenance_repair_accounting.group_finance_maintenance_approver"):
            raise AccessError(_("Only Finance can approve a zero-cost exception."))
        for line in self:
            if line.company_id.legacy_zero_cost_policy != "finance_exception":
                raise UserError(_("The company zero-cost policy does not allow exceptions."))
            if line.legacy_zero_cost_exception_value <= 0 or not (line.legacy_zero_cost_exception_reason or "").strip():
                raise ValidationError(_("An approved value and reason are required."))
            line.write({"legacy_zero_cost_approved_by_id": self.env.user.id, "legacy_zero_cost_approved_date": fields.Datetime.now()})
        return True

    def _legacy_consumption_value(self):
        self.ensure_one()
        amount = abs(sum(self.legacy_repair_move_id.stock_valuation_layer_ids.mapped("value")))
        if not float_is_zero(amount, precision_rounding=self.currency_id.rounding):
            return amount
        if self.company_id.legacy_zero_cost_policy == "finance_exception" and self.legacy_zero_cost_approved_by_id and self.legacy_zero_cost_exception_value > 0:
            return self.legacy_zero_cost_exception_value
        raise UserError(_("The completed stock move has zero value. Finance must resolve the zero-cost exception before posting."))

    def action_post_legacy_return(self):
        self.ensure_one()
        if self.legacy_return_entry_id:
            return self.legacy_return_entry_id
        return_move = self.legacy_return_move_id or self.legacy_repair_move_id.returned_move_ids.filtered(
            lambda move: move.state == "done" and move.legacy_stock_request_line_id == self
        )[:1]
        if not return_move:
            raise UserError(_("Complete the material return before posting its accounting."))
        if self.product_id.valuation == "real_time":
            account_move = return_move.stock_valuation_layer_ids.account_move_id[:1]
            if not account_move:
                raise UserError(_("The automated valuation return entry was not created."))
            self.write({"legacy_return_entry_id": account_move.id, "legacy_accounting_status": "reversed"})
            return account_move
        original_value = self._legacy_consumption_value()
        ratio = return_move.quantity / self.legacy_consumed_quantity if self.legacy_consumed_quantity else 0.0
        amount = self.currency_id.round(original_value * ratio)
        company = self.company_id
        config = company._legacy_check_material_configuration(self.legacy_expense_type, automated=False)
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "date": fields.Date.context_today(self),
                "journal_id": config["journal"].id,
                "ref": _("Return %(request)s - %(product)s", request=self.order_id.display_name, product=self.product_id.display_name),
                "legacy_posting_type": "material_return",
                "legacy_material_request_id": self.order_id.id,
                "legacy_stock_request_line_id": self.id,
                "legacy_repair_order_id": self.legacy_repair_order_id.id,
                "legacy_maintenance_request_id": self.order_id.legacy_maintenance_request_id.id,
                "legacy_equipment_id": self.legacy_equipment_id.id,
                "line_ids": [
                    (0, 0, {"name": self.product_id.display_name, "account_id": config["inventory_account"].id, "debit": amount, "credit": 0.0, "legacy_stock_request_line_id": self.id, "legacy_equipment_id": self.legacy_equipment_id.id, "legacy_workcenter_id": self.legacy_workcenter_id.id}),
                    (0, 0, {"name": self.product_id.display_name, "account_id": config["debit_account"].id, "debit": 0.0, "credit": amount, "legacy_stock_request_line_id": self.id, "legacy_equipment_id": self.legacy_equipment_id.id, "legacy_workcenter_id": self.legacy_workcenter_id.id}),
                ],
            }
        )
        move.action_post()
        self.write({"legacy_return_entry_id": move.id, "legacy_accounting_status": "reversed", "legacy_return_move_id": return_move.id})
        return move


class StockRequestOrder(models.Model):
    _inherit = "stock.request.order"

    legacy_material_posting_move_id = fields.Many2one("account.move", string="Material Posting", copy=False, readonly=True, check_company=True, ondelete="restrict")

    def action_post_legacy_materials(self):
        if not self.env.user.has_group("legacy_maintenance_repair_accounting.group_finance_maintenance_approver"):
            raise AccessError(_("Only Finance can post maintenance material cost."))
        self.ensure_one()
        lines = self.stock_request_ids.filtered(lambda line: line.legacy_fulfillment_owner == "repair" and line.legacy_repair_move_id.state == "done")
        if not lines:
            raise UserError(_("No completed Repair material consumption was found."))
        if any(line.legacy_finance_approval_state != "approved" for line in lines):
            raise UserError(_("Every material line must be Finance approved."))
        manual_lines = lines.filtered(lambda line: line.product_id.valuation != "real_time" and not line.legacy_journal_entry_id)
        for line in lines.filtered(lambda item: item.product_id.valuation == "real_time"):
            account_move = line.legacy_repair_move_id.stock_valuation_layer_ids.account_move_id[:1]
            if not account_move:
                raise UserError(_("Automated valuation did not create an account move for %(product)s.", product=line.product_id.display_name))
            line.write({"legacy_journal_entry_id": account_move.id, "legacy_accounting_status": "posted"})
        posting_move = self.legacy_material_posting_move_id
        if manual_lines and not posting_move:
            line_values = []
            journal = False
            for line in manual_lines:
                config = line.company_id._legacy_check_material_configuration(line.legacy_expense_type, automated=False)
                journal = journal or config["journal"]
                if journal != config["journal"]:
                    raise ValidationError(_("All manual material lines in one requisition must use the same journal."))
                amount = line._legacy_consumption_value()
                common = {"name": "%s - %s" % (self.display_name, line.product_id.display_name), "legacy_stock_request_line_id": line.id, "legacy_equipment_id": line.legacy_equipment_id.id, "legacy_workcenter_id": line.legacy_workcenter_id.id}
                line_values.extend(
                    [
                        (0, 0, dict(common, account_id=config["debit_account"].id, debit=amount, credit=0.0)),
                        (0, 0, dict(common, account_id=config["inventory_account"].id, debit=0.0, credit=amount)),
                    ]
                )
            posting_move = self.env["account.move"].create(
                {
                    "move_type": "entry",
                    "date": fields.Date.context_today(self),
                    "journal_id": journal.id,
                    "ref": _("Material consumption %(request)s", request=self.display_name),
                    "legacy_posting_type": "material",
                    "legacy_material_request_id": self.id,
                    "legacy_repair_order_id": self.legacy_repair_order_id.id,
                    "legacy_maintenance_request_id": self.legacy_maintenance_request_id.id,
                    "legacy_equipment_id": self.legacy_equipment_id.id,
                    "line_ids": line_values,
                }
            )
            posting_move.action_post()
            manual_lines.write({"legacy_journal_entry_id": posting_move.id, "legacy_accounting_status": "posted"})
            self.legacy_material_posting_move_id = posting_move
        self.legacy_accounting_status = "posted" if all(line.legacy_accounting_status == "posted" for line in lines) else "partially_posted"
        self.legacy_repair_order_id._legacy_refresh_accounting_status()
        return posting_move or lines.mapped("legacy_journal_entry_id")[:1]


class RepairOrder(models.Model):
    _inherit = "repair.order"

    legacy_labour_posting_move_ids = fields.Many2many("account.move", "legacy_repair_labour_posting_move_rel", "repair_order_id", "move_id", string="Labour Postings", copy=False, readonly=True)

    def action_post_legacy_labour(self):
        if not self.env.user.has_group("legacy_maintenance_repair_accounting.group_finance_maintenance_approver"):
            raise AccessError(_("Only Finance can post maintenance labour."))
        self.ensure_one()
        lines = self.legacy_labour_ids.filtered(lambda line: line.approval_state == "approved" and line.accounting_status == "not_posted")
        if not lines:
            return self.legacy_labour_posting_move_ids[:1]
        if self.company_id.legacy_labour_posting_mode == "reporting":
            lines.write({"accounting_status": "posted"})
            self.message_post(body=_("Approved labour was finalized in Reporting Only mode; no journal entry was created."), subtype_xmlid="mail.mt_note")
            self._legacy_refresh_accounting_status()
            return self.env["account.move"]
        company = self.company_id
        journal = company._legacy_validate_journal(company.legacy_labour_journal_id, _("Maintenance Labour Journal"))
        credit_account = company._legacy_validate_account(company.legacy_labour_clearing_account_id, _("Labour Clearing Account"))
        values = []
        total = 0.0
        for line in lines:
            debit_account = company._legacy_validate_account(
                company.legacy_cwip_account_id if line.expense_type == "capex" else company.legacy_repair_expense_account_id,
                _("CWIP Account") if line.expense_type == "capex" else _("Repair Expense Account"),
            )
            amount = line.labour_cost
            total += amount
            values.append((0, 0, {"name": "%s - %s" % (self.display_name, line.employee_id.display_name), "account_id": debit_account.id, "debit": amount, "credit": 0.0, "legacy_labour_id": line.id, "legacy_equipment_id": self.legacy_equipment_id.id, "legacy_workcenter_id": (self.legacy_workcenter_id or self.legacy_target_workcenter_id).id}))
        values.append((0, 0, {"name": _("Maintenance labour clearing"), "account_id": credit_account.id, "debit": 0.0, "credit": total, "legacy_equipment_id": self.legacy_equipment_id.id, "legacy_workcenter_id": (self.legacy_workcenter_id or self.legacy_target_workcenter_id).id}))
        move = self.env["account.move"].create(
            {"move_type": "entry", "date": fields.Date.context_today(self), "journal_id": journal.id, "ref": _("Labour %(order)s", order=self.display_name), "legacy_posting_type": "labour", "legacy_repair_order_id": self.id, "legacy_maintenance_request_id": self.legacy_maintenance_request_id.id, "legacy_equipment_id": self.legacy_equipment_id.id, "line_ids": values}
        )
        move.action_post()
        lines.write({"journal_entry_id": move.id, "accounting_status": "posted"})
        self.legacy_labour_posting_move_ids = [(4, move.id)]
        self._legacy_refresh_accounting_status()
        return move

    def action_reverse_legacy_labour(self):
        self.ensure_one()
        posted = self.legacy_labour_posting_move_ids.filtered(lambda move: move.state == "posted")
        if not posted:
            return self.env["account.move"]
        reversals = posted._reverse_moves([{"date": fields.Date.context_today(self), "ref": _("Reversal of %(ref)s", ref=move.ref)} for move in posted], cancel=False)
        self.legacy_labour_ids.filtered(lambda line: line.journal_entry_id in posted).write({"accounting_status": "reversed"})
        self._legacy_refresh_accounting_status()
        return reversals

    def _legacy_refresh_accounting_status(self):
        for order in self:
            material_lines = order.legacy_material_request_ids.stock_request_ids.filtered(lambda line: line.legacy_repair_move_id.state == "done")
            labour_lines = order.legacy_labour_ids.filtered(lambda line: line.approval_state == "approved")
            statuses = material_lines.mapped("legacy_accounting_status") + labour_lines.mapped("accounting_status")
            if not statuses:
                status = "not_posted"
            elif all(item == "reversed" for item in statuses):
                status = "reversed"
            elif all(item == "posted" for item in statuses):
                status = "posted"
            elif any(item in ("posted", "reversed") for item in statuses):
                status = "partially_posted"
            else:
                status = "not_posted"
            order.legacy_accounting_status = status
            if order.legacy_maintenance_request_id:
                order.legacy_maintenance_request_id.legacy_accounting_status = status
