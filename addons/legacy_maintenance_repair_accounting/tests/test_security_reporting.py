from datetime import datetime, timedelta

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "legacy_security_reporting")
class TestSecurityReporting(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.other_company = cls.env["res.company"].create({"name": "Security Other Company", "sequence_prefix": "SOC"})
        cls.workcenter = cls.env["mrp.workcenter"].create({"name": "Security Centre", "company_id": cls.company.id})
        cls.order = cls.env["repair.order"].create({"legacy_order_type": "build", "legacy_target_workcenter_id": cls.workcenter.id, "legacy_machine_name": "Security Machine", "company_id": cls.company.id})
        cls.requester = cls.env["res.users"].create({"name": "Request Only", "login": "legacy_request_only", "company_id": cls.company.id, "company_ids": [(6, 0, cls.company.ids)], "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])]})
        cls.stores = cls.env["res.users"].create({"name": "Stores Only", "login": "legacy_stores_only", "company_id": cls.company.id, "company_ids": [(6, 0, cls.company.ids)], "groups_id": [(6, 0, [cls.env.ref("stock.group_stock_user").id])]})
        cls.technician = cls.env["res.users"].create({"name": "Labour Technician", "login": "legacy_labour_tech", "company_id": cls.company.id, "company_ids": [(6, 0, cls.company.ids)], "groups_id": [(6, 0, [cls.env.ref("legacy_maintenance_repair_accounting.group_labour_user").id])]})

    def test_01_requester_cannot_finance_approve_and_stores_cannot_capitalize(self):
        with self.assertRaises(AccessError):
            self.env["stock.request.order"].with_user(self.requester).action_approve_legacy_finance()
        with self.assertRaises(AccessError):
            self.order.with_user(self.stores).action_open_legacy_capitalization()

    def test_02_technician_cannot_change_hourly_rate(self):
        operation = self.env["legacy.repair.operation"].create({"repair_order_id": self.order.id, "name": "Security operation"})
        employee = self.env["hr.employee"].create({"name": "Security Employee", "company_id": self.company.id, "legacy_maintenance_hourly_rate": 50.0})
        start = datetime(2026, 1, 1, 8)
        labour = self.env["legacy.repair.labour"].create({"repair_order_id": self.order.id, "operation_id": operation.id, "employee_id": employee.id, "start_datetime": start, "end_datetime": start + timedelta(hours=1), "manual_adjustment_reason": "Security test"})
        with self.assertRaises(AccessError):
            labour.with_user(self.technician).write({"hourly_rate": 999.0})

    def test_03_reconciliation_respects_allowed_companies(self):
        other_wc = self.env["mrp.workcenter"].with_company(self.other_company).create({"name": "Other Security Centre", "company_id": self.other_company.id})
        other_order = self.env["repair.order"].with_company(self.other_company).create({"legacy_order_type": "build", "legacy_target_workcenter_id": other_wc.id, "legacy_machine_name": "Other Security Machine", "company_id": self.other_company.id})
        visible = self.env["legacy.repair.cost.reconciliation"].with_user(self.requester).search([])
        self.assertIn(self.order.id, visible.mapped("repair_order_id").ids)
        self.assertNotIn(other_order.id, visible.mapped("repair_order_id").ids)

    def test_04_posted_entry_cannot_be_deleted(self):
        debit = self.env["account.account"].create({"name": "Security Debit", "code": "SEC001", "account_type": "asset_current", "company_id": self.company.id})
        credit = self.env["account.account"].create({"name": "Security Credit", "code": "SEC002", "account_type": "liability_current", "company_id": self.company.id})
        journal = self.env["account.journal"].create({"name": "Security Journal", "code": "SECJ", "type": "general", "company_id": self.company.id})
        move = self.env["account.move"].create({"move_type": "entry", "journal_id": journal.id, "line_ids": [(0, 0, {"name": "Security", "account_id": debit.id, "debit": 10.0}), (0, 0, {"name": "Security", "account_id": credit.id, "credit": 10.0})]})
        move.action_post()
        with self.assertRaises(UserError):
            move.unlink()
