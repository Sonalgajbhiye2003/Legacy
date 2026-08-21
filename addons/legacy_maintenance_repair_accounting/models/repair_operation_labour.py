from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare

from .common import ACCOUNTING_STATUS_SELECTION, EXPENSE_TYPE_SELECTION


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    legacy_maintenance_hourly_rate = fields.Monetary(
        string="Maintenance Hourly Cost",
        currency_field="currency_id",
        groups="hr.group_hr_manager,legacy_maintenance_repair_accounting.group_finance_maintenance_approver",
        help="Optional employee-specific rate copied to new Repair labour entries.",
    )
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)


class LegacyRepairOperation(models.Model):
    _name = "legacy.repair.operation"
    _description = "Repair/Build Operation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "repair_order_id, sequence, id"

    repair_order_id = fields.Many2one("repair.order", required=True, index=True, ondelete="cascade", check_company=True, tracking=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Operation Name", required=True, tracking=True, index="trigram")
    description = fields.Text()
    maintenance_team_id = fields.Many2one("maintenance.team", string="Responsible Team", check_company=True)
    supervisor_id = fields.Many2one("res.users", check_company=True, tracking=True)
    workcenter_id = fields.Many2one("mrp.workcenter", string="Work Centre", required=True, check_company=True, tracking=True)
    planned_start = fields.Datetime(tracking=True)
    planned_end = fields.Datetime(tracking=True)
    actual_start = fields.Datetime(readonly=True, copy=False, tracking=True)
    actual_end = fields.Datetime(readonly=True, copy=False, tracking=True)
    planned_hours = fields.Float()
    actual_approved_hours = fields.Float(compute="_compute_costs", store=True)
    workcenter_hourly_rate = fields.Monetary(string="Work-Centre Hourly Rate Snapshot", currency_field="currency_id", readonly=True)
    labour_cost = fields.Monetary(compute="_compute_costs", store=True, currency_field="currency_id")
    resource_cost = fields.Monetary(compute="_compute_costs", store=True, currency_field="currency_id")
    total_cost = fields.Monetary(compute="_compute_costs", store=True, currency_field="currency_id")
    expense_type = fields.Selection(EXPENSE_TYPE_SELECTION, required=True, tracking=True)
    state = fields.Selection(
        [("draft", "Draft"), ("ready", "Ready"), ("in_progress", "In Progress"), ("paused", "Paused"), ("done", "Done"), ("cancelled", "Cancelled")],
        required=True,
        default="draft",
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(related="repair_order_id.company_id", store=True, index=True, readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    notes = fields.Text()
    labour_ids = fields.One2many("legacy.repair.labour", "operation_id", string="Labour Entries")

    @api.model_create_multi
    def create(self, vals_list):
        orders = self.env["repair.order"].browse([vals.get("repair_order_id") for vals in vals_list if vals.get("repair_order_id")])
        order_map = {order.id: order for order in orders}
        for values in vals_list:
            order = order_map.get(values.get("repair_order_id"))
            if order:
                workcenter = self.env["mrp.workcenter"].browse(values.get("workcenter_id")) if values.get("workcenter_id") else order.legacy_workcenter_id or order.legacy_target_workcenter_id
                values.setdefault("workcenter_id", workcenter.id)
                values.setdefault("workcenter_hourly_rate", workcenter.costs_hour)
                values.setdefault("expense_type", order.legacy_finance_expense_type or order.legacy_proposed_expense_type)
        return super().create(vals_list)

    @api.depends("labour_ids.approval_state", "labour_ids.actual_hours", "labour_ids.labour_cost", "workcenter_hourly_rate")
    def _compute_costs(self):
        for operation in self:
            approved = operation.labour_ids.filtered(lambda line: line.approval_state == "approved")
            operation.actual_approved_hours = sum(approved.mapped("actual_hours"))
            operation.labour_cost = sum(approved.mapped("labour_cost"))
            operation.resource_cost = operation.actual_approved_hours * operation.workcenter_hourly_rate
            operation.total_cost = operation.labour_cost + operation.resource_cost

    @api.constrains("planned_start", "planned_end", "planned_hours", "company_id", "workcenter_id")
    def _check_operation_values(self):
        for operation in self:
            if operation.planned_end and operation.planned_start and operation.planned_end < operation.planned_start:
                raise ValidationError(_("Planned End cannot be before Planned Start."))
            if operation.planned_hours < 0:
                raise ValidationError(_("Planned Hours cannot be negative."))
            if operation.workcenter_id.company_id != operation.company_id:
                raise ValidationError(_("Operation and Work Centre must belong to the same company."))

    def action_ready(self):
        for operation in self:
            if operation.state == "draft":
                operation.state = "ready"
        return True

    def action_start(self):
        for operation in self:
            if operation.state in ("ready", "paused"):
                operation.write({"state": "in_progress", "actual_start": operation.actual_start or fields.Datetime.now()})
            elif operation.state != "in_progress":
                raise UserError(_("Only Ready or Paused operations can be started."))
        return True

    def action_pause(self):
        for operation in self:
            if operation.state == "in_progress":
                operation.state = "paused"
            elif operation.state != "paused":
                raise UserError(_("Only an In Progress operation can be paused."))
        return True

    def action_done(self):
        for operation in self:
            if operation.state == "done":
                continue
            if operation.state not in ("in_progress", "paused"):
                raise UserError(_("Only an active operation can be completed."))
            operation.write({"state": "done", "actual_end": fields.Datetime.now()})
        return True

    def action_cancel(self):
        for operation in self.filtered(lambda item: item.state != "done"):
            operation.state = "cancelled"
        return True


class LegacyRepairLabour(models.Model):
    _name = "legacy.repair.labour"
    _description = "Repair/Build Labour Entry"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "work_date desc, id desc"

    repair_order_id = fields.Many2one("repair.order", required=True, index=True, ondelete="cascade", check_company=True, tracking=True)
    operation_id = fields.Many2one("legacy.repair.operation", required=True, index=True, ondelete="restrict", check_company=True, tracking=True)
    employee_id = fields.Many2one("hr.employee", required=True, index=True, check_company=True, tracking=True)
    department_id = fields.Many2one("hr.department", string="Department Snapshot", check_company=True, readonly=True)
    work_date = fields.Date(required=True, default=fields.Date.context_today, index=True)
    start_datetime = fields.Datetime(tracking=True)
    end_datetime = fields.Datetime(tracking=True)
    break_duration = fields.Float(string="Break Duration (Hours)", default=0.0)
    paused_hours = fields.Float(readonly=True, copy=False)
    pause_started_at = fields.Datetime(readonly=True, copy=False)
    actual_hours = fields.Float(compute="_compute_actual_hours", store=True, digits=(16, 4))
    hourly_rate = fields.Monetary(string="Hourly Cost Rate Snapshot", required=True, currency_field="currency_id", groups="hr.group_hr_manager,legacy_maintenance_repair_accounting.group_finance_maintenance_approver")
    labour_cost = fields.Monetary(compute="_compute_labour_cost", store=True, currency_field="currency_id")
    expense_type = fields.Selection(EXPENSE_TYPE_SELECTION, required=True, tracking=True)
    approval_state = fields.Selection(
        [("draft", "Draft"), ("submitted", "Submitted"), ("approved", "Approved"), ("rejected", "Rejected")],
        required=True,
        default="draft",
        tracking=True,
        index=True,
    )
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    approved_date = fields.Datetime(readonly=True, copy=False)
    accounting_status = fields.Selection(ACCOUNTING_STATUS_SELECTION, required=True, default="not_posted", tracking=True, copy=False)
    journal_entry_id = fields.Many2one("account.move", check_company=True, readonly=True, copy=False, ondelete="restrict")
    company_id = fields.Many2one(related="repair_order_id.company_id", store=True, index=True, readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    is_manual = fields.Boolean(default=False, tracking=True)
    manual_adjustment_reason = fields.Text(tracking=True)
    allow_overlap = fields.Boolean(groups="legacy_maintenance_repair_accounting.group_labour_approver")
    notes = fields.Text()
    timer_state = fields.Selection(
        [("stopped", "Not Started"), ("running", "Running"), ("paused", "Paused"), ("finished", "Finished")],
        required=True,
        default="stopped",
        copy=False,
        index=True,
    )
    running_key = fields.Char(copy=False, index=True, readonly=True)

    _sql_constraints = [
        ("running_employee_unique", "unique(running_key)", "An employee already has an active Repair labour timer."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        employee_ids = [values.get("employee_id") for values in vals_list if values.get("employee_id")]
        employees = {employee.id: employee for employee in self.env["hr.employee"].browse(employee_ids)}
        operation_ids = [values.get("operation_id") for values in vals_list if values.get("operation_id")]
        operations = {operation.id: operation for operation in self.env["legacy.repair.operation"].browse(operation_ids)}
        for values in vals_list:
            employee = employees.get(values.get("employee_id"))
            operation = operations.get(values.get("operation_id"))
            if operation:
                values.setdefault("repair_order_id", operation.repair_order_id.id)
                values.setdefault("expense_type", operation.expense_type)
            if employee:
                values.setdefault("department_id", employee.department_id.id)
                values.setdefault("hourly_rate", employee.legacy_maintenance_hourly_rate or employee.company_id.legacy_default_labour_hourly_rate)
            if values.get("start_datetime") and values.get("end_datetime"):
                values.setdefault("is_manual", True)
                values.setdefault("timer_state", "finished")
        return super().create(vals_list)

    @api.depends("start_datetime", "end_datetime", "break_duration", "paused_hours")
    def _compute_actual_hours(self):
        for labour in self:
            if labour.start_datetime and labour.end_datetime:
                elapsed = (labour.end_datetime - labour.start_datetime).total_seconds() / 3600.0
                labour.actual_hours = max(0.0, elapsed - labour.break_duration - labour.paused_hours)
            else:
                labour.actual_hours = 0.0

    @api.depends("actual_hours", "hourly_rate", "approval_state")
    def _compute_labour_cost(self):
        for labour in self:
            labour.labour_cost = labour.actual_hours * labour.hourly_rate if labour.approval_state == "approved" else 0.0

    @api.constrains("operation_id", "repair_order_id", "employee_id", "company_id", "start_datetime", "end_datetime", "break_duration", "is_manual", "manual_adjustment_reason")
    def _check_labour_values(self):
        for labour in self:
            if labour.operation_id.repair_order_id != labour.repair_order_id:
                raise ValidationError(_("Labour Operation and Repair/Build Order must match."))
            if labour.employee_id.company_id != labour.company_id:
                raise ValidationError(_("Employee and Repair/Build Order must belong to the same company."))
            if labour.end_datetime and labour.start_datetime and labour.end_datetime < labour.start_datetime:
                raise ValidationError(_("Labour End cannot be before Start."))
            if labour.break_duration < 0:
                raise ValidationError(_("Break Duration cannot be negative."))
            if labour.is_manual and not (labour.manual_adjustment_reason or "").strip():
                raise ValidationError(_("Manual Adjustment Reason is required for manual labour."))
            if labour.start_datetime and labour.end_datetime and not labour.allow_overlap:
                overlap = self.search_count(
                    [
                        ("id", "!=", labour.id),
                        ("employee_id", "=", labour.employee_id.id),
                        ("company_id", "=", labour.company_id.id),
                        ("start_datetime", "<", labour.end_datetime),
                        ("end_datetime", ">", labour.start_datetime),
                        ("approval_state", "!=", "rejected"),
                    ],
                    limit=1,
                )
                if overlap:
                    raise ValidationError(_("This labour entry overlaps another entry for the employee."))

    def action_start_timer(self, at=None):
        self.ensure_one()
        if self.timer_state == "running":
            return self
        if self.timer_state != "stopped":
            raise UserError(_("Only a new labour timer can be started."))
        at = at or fields.Datetime.now()
        self.write({"start_datetime": at, "work_date": at.date(), "timer_state": "running", "running_key": "%s:%s" % (self.company_id.id, self.employee_id.id)})
        return self

    def action_pause_timer(self, at=None):
        self.ensure_one()
        if self.timer_state == "paused":
            return self
        if self.timer_state != "running":
            raise UserError(_("Only a running labour timer can be paused."))
        self.write({"timer_state": "paused", "pause_started_at": at or fields.Datetime.now()})
        return self

    def action_resume_timer(self, at=None):
        self.ensure_one()
        if self.timer_state == "running":
            return self
        if self.timer_state != "paused":
            raise UserError(_("Only a paused labour timer can be resumed."))
        at = at or fields.Datetime.now()
        paused = max(0.0, (at - self.pause_started_at).total_seconds() / 3600.0)
        self.write({"timer_state": "running", "paused_hours": self.paused_hours + paused, "pause_started_at": False})
        return self

    def action_finish_timer(self, at=None):
        self.ensure_one()
        if self.timer_state == "finished":
            return self
        if self.timer_state not in ("running", "paused"):
            raise UserError(_("Only an active labour timer can be finished."))
        at = at or fields.Datetime.now()
        paused_hours = self.paused_hours
        if self.timer_state == "paused" and self.pause_started_at:
            paused_hours += max(0.0, (at - self.pause_started_at).total_seconds() / 3600.0)
        self.write({"end_datetime": at, "timer_state": "finished", "paused_hours": paused_hours, "pause_started_at": False, "running_key": False})
        return self

    def action_submit(self):
        for labour in self:
            if labour.timer_state != "finished" or labour.actual_hours <= 0:
                raise UserError(_("Finish the labour entry before submission."))
            if labour.approval_state == "draft":
                labour.approval_state = "submitted"
        return True

    def action_approve(self):
        if not (self.env.user.has_group("legacy_maintenance_repair_accounting.group_labour_approver") or self.env.user.has_group("legacy_maintenance_repair_accounting.group_repair_supervisor")):
            raise AccessError(_("Only a Labour Approver can approve labour."))
        for labour in self:
            if labour.approval_state == "approved":
                continue
            if labour.approval_state != "submitted":
                raise UserError(_("Only submitted labour can be approved."))
            labour.write({"approval_state": "approved", "approved_by_id": self.env.user.id, "approved_date": fields.Datetime.now()})
            labour.message_post(body=_("Labour approved by %(user)s.", user=self.env.user.display_name), subtype_xmlid="mail.mt_note")
        return True

    def action_reject(self):
        for labour in self:
            if labour.approval_state == "submitted":
                labour.approval_state = "rejected"
        return True


class RepairOrder(models.Model):
    _inherit = "repair.order"

    legacy_operation_ids = fields.One2many("legacy.repair.operation", "repair_order_id", string="Operations")
    legacy_labour_ids = fields.One2many("legacy.repair.labour", "repair_order_id", string="Labour Entries")
    legacy_labour_count = fields.Integer(string="Labour Count", compute="_compute_legacy_labour_totals", store=True, compute_sudo=False)
    legacy_material_cost = fields.Monetary(compute="_compute_legacy_labour_totals", currency_field="currency_id", store=True, compute_sudo=False)
    legacy_labour_cost = fields.Monetary(compute="_compute_legacy_labour_totals", currency_field="currency_id", store=True, compute_sudo=False)
    legacy_total_capex = fields.Monetary(compute="_compute_legacy_labour_totals", currency_field="currency_id", store=True, compute_sudo=False)
    legacy_total_opex = fields.Monetary(compute="_compute_legacy_labour_totals", currency_field="currency_id", store=True, compute_sudo=False)

    @api.depends(
        "legacy_labour_ids.approval_state",
        "legacy_labour_ids.labour_cost",
        "legacy_labour_ids.expense_type",
        "legacy_material_request_ids.stock_request_ids.legacy_posted_value",
        "legacy_material_request_ids.stock_request_ids.legacy_expense_type",
    )
    def _compute_legacy_labour_totals(self):
        for order in self:
            approved = order.legacy_labour_ids.filtered(lambda line: line.approval_state == "approved")
            material_lines = order.legacy_material_request_ids.stock_request_ids.filtered(lambda line: line.legacy_repair_move_id.state == "done")
            order.legacy_labour_count = len(order.legacy_labour_ids)
            order.legacy_material_cost = sum(material_lines.mapped("legacy_posted_value"))
            order.legacy_labour_cost = sum(approved.mapped("labour_cost"))
            order.legacy_total_capex = sum(approved.filtered(lambda line: line.expense_type == "capex").mapped("labour_cost")) + sum(material_lines.filtered(lambda line: line.legacy_expense_type == "capex").mapped("legacy_posted_value"))
            order.legacy_total_opex = sum(approved.filtered(lambda line: line.expense_type == "opex").mapped("labour_cost")) + sum(material_lines.filtered(lambda line: line.legacy_expense_type == "opex").mapped("legacy_posted_value"))

    def action_view_legacy_labour(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("legacy_maintenance_repair_accounting.action_repair_labour")
        action["domain"] = [("repair_order_id", "=", self.id)]
        action["context"] = {"default_repair_order_id": self.id}
        return action
