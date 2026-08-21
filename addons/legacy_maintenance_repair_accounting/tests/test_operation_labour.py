from datetime import datetime, timedelta

from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "legacy_operation_labour")
class TestOperationLabour(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.env.user.write({"groups_id": [(4, cls.env.ref("legacy_maintenance_repair_accounting.group_labour_approver").id)]})
        cls.company.legacy_default_labour_hourly_rate = 100.0
        cls.workcenter = cls.env["mrp.workcenter"].create({"name": "Labour Test Centre", "company_id": cls.company.id, "costs_hour": 25.0})
        cls.employee = cls.env["hr.employee"].create({"name": "Labour Test Employee", "company_id": cls.company.id, "legacy_maintenance_hourly_rate": 120.0})
        cls.order = cls.env["repair.order"].create({"legacy_order_type": "build", "legacy_target_workcenter_id": cls.workcenter.id, "legacy_machine_name": "Test Machine", "company_id": cls.company.id})
        cls.operation = cls.env["legacy.repair.operation"].create({"repair_order_id": cls.order.id, "name": "Assembly"})

    def _labour(self, **values):
        data = {"repair_order_id": self.order.id, "operation_id": self.operation.id, "employee_id": self.employee.id}
        data.update(values)
        return self.env["legacy.repair.labour"].create(data)

    def test_01_operation_lifecycle_and_defaults(self):
        self.assertEqual(self.operation.expense_type, "capex")
        self.assertEqual(self.operation.workcenter_hourly_rate, 25.0)
        self.operation.action_ready(); self.operation.action_start(); self.operation.action_pause(); self.operation.action_start(); self.operation.action_done()
        self.assertEqual(self.operation.state, "done")

    def test_02_timer_pause_finish_and_idempotency(self):
        start = datetime(2026, 1, 1, 8, 0, 0)
        labour = self._labour()
        labour.action_start_timer(start); labour.action_start_timer(start)
        labour.action_pause_timer(start + timedelta(hours=1))
        labour.action_resume_timer(start + timedelta(hours=1, minutes=30))
        labour.action_finish_timer(start + timedelta(hours=3))
        labour.action_finish_timer(start + timedelta(hours=3))
        self.assertAlmostEqual(labour.actual_hours, 2.5, places=4)

    def test_03_one_active_timer_per_employee(self):
        first = self._labour(); second = self._labour()
        first.action_start_timer(datetime(2026, 1, 2, 8, 0, 0))
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            second.action_start_timer(datetime(2026, 1, 2, 9, 0, 0))

    def test_04_manual_reason_and_overlap(self):
        start = datetime(2026, 1, 3, 8, 0, 0)
        with self.assertRaises(ValidationError):
            self._labour(start_datetime=start, end_datetime=start + timedelta(hours=1))
        self._labour(start_datetime=start, end_datetime=start + timedelta(hours=1), manual_adjustment_reason="Call-out correction")
        with self.assertRaises(ValidationError):
            self._labour(start_datetime=start + timedelta(minutes=30), end_datetime=start + timedelta(hours=2), manual_adjustment_reason="Overlap")

    def test_05_rate_snapshot_approval_and_cost(self):
        start = datetime(2026, 1, 4, 8, 0, 0)
        labour = self._labour(start_datetime=start, end_datetime=start + timedelta(hours=2), manual_adjustment_reason="Approved manual work")
        self.assertEqual(labour.hourly_rate, 120.0)
        self.employee.legacy_maintenance_hourly_rate = 200.0
        self.assertEqual(labour.hourly_rate, 120.0)
        labour.action_submit(); labour.action_approve()
        self.assertEqual(labour.labour_cost, 240.0)
        self.assertEqual(self.order.legacy_labour_cost, 240.0)

    def test_06_no_project_timesheet_or_mrp_records(self):
        model_names = set(self.env["ir.model"].search([("model", "in", ["project.project", "project.task", "account.analytic.line", "mrp.production"])]).mapped("model"))
        before = {name: self.env[name].search_count([]) for name in model_names}
        labour = self._labour(); labour.action_start_timer(datetime(2026, 1, 5, 8)); labour.action_finish_timer(datetime(2026, 1, 5, 9))
        after = {name: self.env[name].search_count([]) for name in model_names}
        self.assertEqual(before, after)
