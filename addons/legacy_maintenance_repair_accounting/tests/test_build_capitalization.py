from datetime import datetime, timedelta

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "legacy_build_capitalization")
class TestBuildCapitalization(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.env.user.write({"groups_id": [(4, cls.env.ref("legacy_maintenance_repair_accounting.group_finance_maintenance_approver").id), (4, cls.env.ref("legacy_maintenance_repair_accounting.group_labour_approver").id)]})
        cls.cwip = cls.env["account.account"].create({"name": "Build Test CWIP", "code": "BLD001", "account_type": "asset_current", "company_id": cls.company.id})
        cls.ppe = cls.env["account.account"].create({"name": "Build Test PPE", "code": "BLD002", "account_type": "asset_fixed", "company_id": cls.company.id})
        cls.clearing = cls.env["account.account"].create({"name": "Build Test Clearing", "code": "BLD003", "account_type": "liability_current", "company_id": cls.company.id})
        cls.journal = cls.env["account.journal"].create({"name": "Build Test Journal", "code": "BLDJ", "type": "general", "company_id": cls.company.id})
        cls.workcenter = cls.env["mrp.workcenter"].create({"name": "Built Machine Centre", "company_id": cls.company.id})
        cls.company.write({"legacy_cwip_account_id": cls.cwip.id, "legacy_ppe_account_id": cls.ppe.id, "legacy_labour_clearing_account_id": cls.clearing.id, "legacy_labour_journal_id": cls.journal.id, "legacy_capitalization_journal_id": cls.journal.id, "legacy_labour_posting_mode": "post_approved"})

    def _ready_build(self):
        request = self.env["maintenance.request"].create({"name": "Build Test Request", "maintenance_for": "workcenter", "workcenter_id": self.workcenter.id, "legacy_work_type": "build", "company_id": self.company.id})
        order = self.env["repair.order"].create({"legacy_order_type": "build", "legacy_maintenance_request_id": request.id, "legacy_target_workcenter_id": self.workcenter.id, "legacy_machine_name": "Commissioned Test Machine", "company_id": self.company.id})
        operation = self.env["legacy.repair.operation"].create({"repair_order_id": order.id, "name": "Assembly"})
        operation.write({"state": "in_progress"}); operation.action_done()
        employee = self.env["hr.employee"].create({"name": "Build Worker", "company_id": self.company.id, "legacy_maintenance_hourly_rate": 100.0})
        start = datetime(2026, 1, 1, 8)
        labour = self.env["legacy.repair.labour"].create({"repair_order_id": order.id, "operation_id": operation.id, "employee_id": employee.id, "start_datetime": start, "end_datetime": start + timedelta(hours=2), "manual_adjustment_reason": "Build test"})
        labour.action_submit(); labour.action_approve(); order.action_post_legacy_labour()
        return order, operation, labour

    def _capitalize(self, order):
        wizard = self.env["legacy.build.capitalization.wizard"].create({"repair_order_id": order.id, "commissioning_date": "2026-01-05", "accounting_date": "2026-01-05"})
        action = wizard.action_capitalize()
        return self.env["account.move"].browse(action["res_id"])

    def test_01_success_equipment_and_idempotency(self):
        order, operation, labour = self._ready_build(); move = self._capitalize(order)
        self.assertEqual(move.state, "posted"); self.assertEqual(move.legacy_posting_type, "capitalization")
        self.assertEqual(sum(move.line_ids.mapped("balance")), 0.0)
        self.assertEqual(order.legacy_equipment_id.workcenter_id, self.workcenter)
        self.assertEqual(order.legacy_equipment_id.legacy_commissioning_state, "in_service")
        self.assertEqual(order.legacy_equipment_id.legacy_capitalized_cost, 200.0)
        self.assertEqual(order.action_open_legacy_capitalization()["res_id"], move.id)

    def test_02_incomplete_operation_blocks(self):
        order, operation, labour = self._ready_build(); operation.state = "ready"
        with self.assertRaises(ValidationError):
            self._capitalize(order)

    def test_03_unapproved_labour_blocks(self):
        order, operation, labour = self._ready_build(); labour.write({"approval_state": "draft", "accounting_status": "not_posted"})
        with self.assertRaises(ValidationError):
            self._capitalize(order)

    def test_04_cwip_mismatch_blocks(self):
        order, operation, labour = self._ready_build()
        mismatch = self.env["account.move"].create({"move_type": "entry", "journal_id": self.journal.id, "date": "2026-01-04", "legacy_repair_order_id": order.id, "legacy_posting_type": "labour", "line_ids": [(0, 0, {"name": "Mismatch", "account_id": self.cwip.id, "debit": 50.0}), (0, 0, {"name": "Mismatch", "account_id": self.clearing.id, "credit": 50.0})]})
        mismatch.action_post()
        with self.assertRaises(ValidationError):
            self._capitalize(order)

    def test_05_reversal_is_controlled(self):
        order, operation, labour = self._ready_build(); move = self._capitalize(order); reversal = order.action_reverse_legacy_capitalization()
        self.assertTrue(reversal); self.assertEqual(order.legacy_capitalization_status, "reversed")
        self.assertEqual(order.legacy_equipment_id.legacy_commissioning_state, "under_construction")
