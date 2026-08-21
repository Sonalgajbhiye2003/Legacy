from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .common import ACCOUNTING_STATUS_SELECTION, EXPENSE_TYPE_SELECTION, FINANCE_APPROVAL_SELECTION, WORK_TYPE_SELECTION


class RepairOrder(models.Model):
    _inherit = "repair.order"

    legacy_order_type = fields.Selection(
        WORK_TYPE_SELECTION,
        string="Order Type",
        required=True,
        default="repair",
        tracking=True,
        index=True,
    )
    legacy_maintenance_request_id = fields.Many2one(
        "maintenance.request",
        string="Maintenance Request",
        copy=False,
        index=True,
        ondelete="restrict",
        check_company=True,
    )
    legacy_equipment_id = fields.Many2one(
        "maintenance.equipment",
        string="Equipment",
        check_company=True,
        tracking=True,
    )
    legacy_workcenter_id = fields.Many2one(
        "mrp.workcenter",
        string="Work Centre",
        check_company=True,
        tracking=True,
    )
    legacy_target_workcenter_id = fields.Many2one(
        "mrp.workcenter",
        string="Target Work Centre",
        check_company=True,
        tracking=True,
    )
    legacy_proposed_expense_type = fields.Selection(
        EXPENSE_TYPE_SELECTION,
        string="Proposed Accounting Treatment",
        tracking=True,
    )
    legacy_machine_name = fields.Char(string="Machine/Equipment Name", tracking=True)
    legacy_finance_expense_type = fields.Selection(
        EXPENSE_TYPE_SELECTION,
        string="Finance-Approved Treatment",
        tracking=True,
        copy=False,
    )
    legacy_finance_approval_state = fields.Selection(
        FINANCE_APPROVAL_SELECTION,
        string="Finance Approval",
        required=True,
        default="draft",
        tracking=True,
        copy=False,
    )
    legacy_accounting_status = fields.Selection(
        ACCOUNTING_STATUS_SELECTION,
        string="Accounting Status",
        required=True,
        default="not_posted",
        tracking=True,
        copy=False,
    )
    legacy_capitalization_status = fields.Selection(
        [
            ("not_applicable", "Not Applicable"),
            ("not_ready", "Not Ready"),
            ("ready", "Ready to Capitalize"),
            ("capitalized", "Capitalized"),
            ("reversed", "Reversed"),
        ],
        string="Capitalization Status",
        required=True,
        default="not_applicable",
        tracking=True,
        copy=False,
    )
    legacy_material_request_ids = fields.One2many(
        "stock.request.order",
        "legacy_repair_order_id",
        string="Material Requisitions",
    )
    legacy_journal_entry_ids = fields.One2many(
        "account.move",
        "legacy_repair_order_id",
        string="Journal Entries",
    )
    legacy_material_request_count = fields.Integer(compute="_compute_legacy_document_counts")
    legacy_journal_entry_count = fields.Integer(compute="_compute_legacy_document_counts")
    legacy_labour_count = fields.Integer(string="Labour Entries", default=0, readonly=True)
    legacy_component_count = fields.Integer(string="Components", default=0, readonly=True)
    legacy_material_cost = fields.Monetary(currency_field="currency_id", default=0.0, readonly=True)
    legacy_labour_cost = fields.Monetary(currency_field="currency_id", default=0.0, readonly=True)
    legacy_total_capex = fields.Monetary(currency_field="currency_id", default=0.0, readonly=True)
    legacy_total_opex = fields.Monetary(currency_field="currency_id", default=0.0, readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)

    _sql_constraints = [
        (
            "legacy_maintenance_request_unique",
            "unique(legacy_maintenance_request_id)",
            "A Maintenance Request can have only one Repair/Build Order.",
        )
    ]

    @api.depends("legacy_material_request_ids", "legacy_journal_entry_ids")
    def _compute_legacy_document_counts(self):
        for order in self:
            order.legacy_material_request_count = len(order.legacy_material_request_ids)
            order.legacy_journal_entry_count = len(order.legacy_journal_entry_ids)

    @api.onchange("legacy_order_type")
    def _onchange_legacy_order_type(self):
        for order in self:
            if order.legacy_order_type == "build":
                order.legacy_equipment_id = False
                order.legacy_workcenter_id = False
                order.legacy_proposed_expense_type = "capex"
                order.legacy_capitalization_status = "not_ready"
            else:
                order.legacy_target_workcenter_id = False
                order.legacy_machine_name = False
                order.legacy_proposed_expense_type = "opex"
                order.legacy_capitalization_status = "not_applicable"

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            order_type = values.get("legacy_order_type", "repair")
            values.setdefault("legacy_proposed_expense_type", "capex" if order_type == "build" else "opex")
            values.setdefault("legacy_capitalization_status", "not_ready" if order_type == "build" else "not_applicable")
        return super().create(vals_list)

    def write(self, values):
        if "legacy_order_type" in values:
            for order in self:
                if order.state != "draft" or order.move_ids.filtered(lambda move: move.state == "done") or order.legacy_journal_entry_ids.filtered(lambda move: move.state == "posted"):
                    raise UserError(_("Order Type cannot change after stock or accounting processing has started."))
        return super().write(values)

    @api.constrains(
        "legacy_order_type",
        "legacy_maintenance_request_id",
        "legacy_equipment_id",
        "legacy_workcenter_id",
        "legacy_target_workcenter_id",
        "company_id",
    )
    def _check_legacy_order_consistency(self):
        for order in self:
            request = order.legacy_maintenance_request_id
            if request and request.legacy_work_type and request.legacy_work_type != order.legacy_order_type:
                raise ValidationError(_("Maintenance Request and Repair/Build Order types must match."))
            for record in (order.legacy_equipment_id, order.legacy_workcenter_id, order.legacy_target_workcenter_id):
                if record.company_id and record.company_id != order.company_id:
                    raise ValidationError(_("Equipment and Work Centres must belong to the Repair/Build Order company."))

    def _legacy_check_ready_for_confirmation(self):
        for order in self:
            if order.legacy_order_type == "repair":
                if not order.legacy_equipment_id:
                    raise ValidationError(_("Equipment is required for Repair Existing Machine."))
                if not order.legacy_workcenter_id:
                    raise ValidationError(_("Work Centre is required for Repair Existing Machine."))
            elif order.legacy_order_type == "build":
                if not order.legacy_target_workcenter_id:
                    raise ValidationError(_("Target Work Centre is required for Build New Machine."))
                if not (order.legacy_machine_name or "").strip():
                    raise ValidationError(_("Machine/Equipment Name is required for Build New Machine."))
            else:
                raise ValidationError(_("Order Type is required."))

    def _action_repair_confirm(self):
        self._legacy_check_ready_for_confirmation()
        return super()._action_repair_confirm()

    def action_view_legacy_maintenance_request(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Maintenance Request"),
            "res_model": "maintenance.request",
            "view_mode": "form",
            "res_id": self.legacy_maintenance_request_id.id,
        }

    def action_view_legacy_material_requests(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("stock_request.stock_request_order_action")
        action["domain"] = [("legacy_repair_order_id", "=", self.id)]
        action["context"] = {
            "default_legacy_repair_order_id": self.id,
            "default_legacy_maintenance_request_id": self.legacy_maintenance_request_id.id,
        }
        return action

    def action_view_legacy_journal_entries(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_journal_line")
        action["domain"] = [("legacy_repair_order_id", "=", self.id)]
        return action
