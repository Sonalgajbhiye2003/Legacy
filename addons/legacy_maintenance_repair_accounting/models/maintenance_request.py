from psycopg2 import IntegrityError

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import mute_logger

from .common import ACCOUNTING_STATUS_SELECTION, EXPENSE_TYPE_SELECTION, FINANCE_APPROVAL_SELECTION, WORK_TYPE_SELECTION


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    legacy_work_type = fields.Selection(
        WORK_TYPE_SELECTION,
        string="Work Type",
        tracking=True,
        index=True,
    )
    legacy_existing_equipment_id = fields.Many2one(
        "maintenance.equipment",
        string="Existing Equipment",
        check_company=True,
        tracking=True,
        domain="[('workcenter_id', 'in', [False, workcenter_id]), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    legacy_repair_order_ids = fields.One2many(
        "repair.order",
        "legacy_maintenance_request_id",
        string="Repair/Build Orders",
    )
    legacy_repair_order_count = fields.Integer(compute="_compute_legacy_counts")
    legacy_material_request_count = fields.Integer(compute="_compute_legacy_counts")
    legacy_journal_entry_count = fields.Integer(compute="_compute_legacy_counts")
    legacy_proposed_expense_type = fields.Selection(
        EXPENSE_TYPE_SELECTION,
        string="Proposed Accounting Treatment",
        tracking=True,
    )
    legacy_finance_expense_type = fields.Selection(
        EXPENSE_TYPE_SELECTION,
        string="Finance-Approved Treatment",
        tracking=True,
        copy=False,
    )
    legacy_finance_approval_state = fields.Selection(
        FINANCE_APPROVAL_SELECTION,
        string="Finance Approval",
        default="draft",
        required=True,
        tracking=True,
        copy=False,
    )
    legacy_accounting_status = fields.Selection(
        ACCOUNTING_STATUS_SELECTION,
        string="Accounting Status",
        default="not_posted",
        required=True,
        tracking=True,
        copy=False,
    )
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    legacy_material_cost = fields.Monetary(compute="_compute_legacy_costs", currency_field="currency_id")
    legacy_labour_cost = fields.Monetary(compute="_compute_legacy_costs", currency_field="currency_id")
    legacy_total_capex = fields.Monetary(compute="_compute_legacy_costs", currency_field="currency_id")
    legacy_total_opex = fields.Monetary(compute="_compute_legacy_costs", currency_field="currency_id")

    @api.depends("legacy_repair_order_ids")
    def _compute_legacy_counts(self):
        request_model = self.env["stock.request.order"]
        move_model = self.env["account.move"]
        mr_counts = request_model._read_group(
            [("legacy_maintenance_request_id", "in", self.ids)],
            ["legacy_maintenance_request_id"],
            ["__count"],
        ) if self.ids else []
        move_counts = move_model._read_group(
            [("legacy_maintenance_request_id", "in", self.ids)],
            ["legacy_maintenance_request_id"],
            ["__count"],
        ) if self.ids else []
        mr_map = {request.id: count for request, count in mr_counts}
        move_map = {request.id: count for request, count in move_counts}
        for request in self:
            request.legacy_repair_order_count = len(request.legacy_repair_order_ids)
            request.legacy_material_request_count = mr_map.get(request.id, 0)
            request.legacy_journal_entry_count = move_map.get(request.id, 0)

    @api.depends(
        "legacy_repair_order_ids.legacy_material_cost",
        "legacy_repair_order_ids.legacy_labour_cost",
        "legacy_repair_order_ids.legacy_total_capex",
        "legacy_repair_order_ids.legacy_total_opex",
    )
    def _compute_legacy_costs(self):
        for request in self:
            orders = request.legacy_repair_order_ids
            request.legacy_material_cost = sum(orders.mapped("legacy_material_cost"))
            request.legacy_labour_cost = sum(orders.mapped("legacy_labour_cost"))
            request.legacy_total_capex = sum(orders.mapped("legacy_total_capex"))
            request.legacy_total_opex = sum(orders.mapped("legacy_total_opex"))

    @api.onchange("maintenance_for", "legacy_work_type")
    def _onchange_legacy_work_type(self):
        for request in self:
            if request.maintenance_for != "workcenter":
                request.legacy_work_type = False
                request.legacy_existing_equipment_id = False
                request.legacy_proposed_expense_type = False
            elif request.legacy_work_type == "build":
                request.legacy_existing_equipment_id = False
                request.legacy_proposed_expense_type = "capex"
            elif request.legacy_work_type == "repair":
                request.legacy_proposed_expense_type = "opex"

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("maintenance_for") == "workcenter" and values.get("legacy_work_type"):
                values.setdefault("legacy_proposed_expense_type", "capex" if values["legacy_work_type"] == "build" else "opex")
        return super().create(vals_list)

    def write(self, values):
        protected = {"maintenance_for", "legacy_work_type", "workcenter_id", "legacy_existing_equipment_id"}
        if protected.intersection(values):
            for request in self:
                if request._legacy_has_locked_transactions():
                    raise UserError(_("Work Type, Work Centre and Equipment cannot change after downstream transactions are confirmed or posted."))
        return super().write(values)

    def _legacy_has_locked_transactions(self):
        self.ensure_one()
        return bool(
            self.legacy_repair_order_ids.filtered(lambda order: order.state != "draft")
            or self.env["account.move"].search_count(
                [("legacy_maintenance_request_id", "=", self.id), ("state", "=", "posted")], limit=1
            )
        )

    @api.constrains("maintenance_for", "legacy_work_type", "workcenter_id", "legacy_existing_equipment_id", "company_id")
    def _check_legacy_work_request(self):
        for request in self:
            if request.maintenance_for != "workcenter":
                continue
            if not request.legacy_work_type:
                raise ValidationError(_("Work Type is required for Work Centre maintenance."))
            if not request.workcenter_id:
                raise ValidationError(_("Work Centre is required."))
            if request.workcenter_id.company_id != request.company_id:
                raise ValidationError(_("Work Centre and Maintenance Request must belong to the same company."))
            if request.legacy_work_type == "repair" and not request.legacy_existing_equipment_id:
                raise ValidationError(_("Existing Equipment is required for Repair Existing Machine."))
            equipment = request.legacy_existing_equipment_id
            if equipment and equipment.company_id and equipment.company_id != request.company_id:
                raise ValidationError(_("Equipment and Maintenance Request must belong to the same company."))

    def action_create_legacy_repair_order(self):
        self.ensure_one()
        if self.maintenance_for != "workcenter" or not self.legacy_work_type:
            raise UserError(_("Select Work Centre maintenance and a Work Type first."))
        self._check_legacy_work_request()
        order = self.legacy_repair_order_ids[:1]
        if not order:
            values = {
                "company_id": self.company_id.id,
                "legacy_order_type": self.legacy_work_type,
                "legacy_maintenance_request_id": self.id,
                "legacy_equipment_id": self.legacy_existing_equipment_id.id,
                "legacy_workcenter_id": self.workcenter_id.id if self.legacy_work_type == "repair" else False,
                "legacy_target_workcenter_id": self.workcenter_id.id if self.legacy_work_type == "build" else False,
                "legacy_proposed_expense_type": self.legacy_proposed_expense_type,
                "user_id": self.user_id.id or self.env.user.id,
                "internal_notes": self.description,
            }
            try:
                with self.env.cr.savepoint(), mute_logger("odoo.sql_db"):
                    order = self.env["repair.order"].create(values)
            except IntegrityError:
                order = self.env["repair.order"].search([("legacy_maintenance_request_id", "=", self.id)], limit=1)
                if not order:
                    raise
            self.message_post(
                body=_("%(type)s %(order)s was created.", type=dict(WORK_TYPE_SELECTION)[self.legacy_work_type], order=order.display_name),
                subtype_xmlid="mail.mt_note",
            )
        return self._legacy_repair_order_action(order)

    def _legacy_repair_order_action(self, order=None):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("repair.action_repair_order_form")
        if order:
            action.update({"view_mode": "form", "views": [(False, "form")], "res_id": order.id})
        else:
            action["domain"] = [("legacy_maintenance_request_id", "=", self.id)]
            action["context"] = {"default_legacy_maintenance_request_id": self.id}
        return action

    def action_view_legacy_repair_orders(self):
        self.ensure_one()
        return self._legacy_repair_order_action(self.legacy_repair_order_ids if len(self.legacy_repair_order_ids) == 1 else None)

    def action_view_legacy_material_requests(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("stock_request.stock_request_order_action")
        action["domain"] = [("legacy_maintenance_request_id", "=", self.id)]
        return action

    def action_view_legacy_journal_entries(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_journal_line")
        action["domain"] = [("legacy_maintenance_request_id", "=", self.id)]
        return action

