from datetime import datetime, timedelta

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "legacy_accounting_engine")
class TestAccountingEngine(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.env.user.write({"groups_id": [(4, cls.env.ref("legacy_maintenance_repair_accounting.group_finance_maintenance_approver").id), (4, cls.env.ref("legacy_maintenance_repair_accounting.group_labour_approver").id)]})
        cls.workcenter = cls.env["mrp.workcenter"].create({"name": "Accounting Test Centre", "company_id": cls.company.id})
        cls.equipment = cls.env["maintenance.equipment"].create({"name": "Accounting Test Machine", "company_id": cls.company.id, "workcenter_id": cls.workcenter.id})
        cls.expense = cls.env["account.account"].create({"name": "Accounting Test Expense", "code": "ACTEST01", "account_type": "expense", "company_id": cls.company.id})
        cls.inventory = cls.env["account.account"].create({"name": "Accounting Test Inventory", "code": "ACTEST02", "account_type": "asset_current", "company_id": cls.company.id})
        cls.clearing = cls.env["account.account"].create({"name": "Accounting Test Clearing", "code": "ACTEST03", "account_type": "liability_current", "company_id": cls.company.id})
        cls.journal = cls.env["account.journal"].create({"name": "Accounting Test Journal", "code": "ACTJ", "type": "general", "company_id": cls.company.id})
        cls.capex_location = cls.env["stock.location"].create({"name": "Accounting CAPEX", "usage": "production", "company_id": cls.company.id})
        cls.opex_location = cls.env["stock.location"].create({"name": "Accounting OPEX", "usage": "production", "company_id": cls.company.id})
        cls.company.write({"legacy_cwip_account_id": cls.inventory.id, "legacy_repair_expense_account_id": cls.expense.id, "legacy_inventory_account_id": cls.inventory.id, "legacy_labour_clearing_account_id": cls.clearing.id, "legacy_material_journal_id": cls.journal.id, "legacy_labour_journal_id": cls.journal.id, "legacy_capitalization_journal_id": cls.journal.id, "legacy_capex_location_id": cls.capex_location.id, "legacy_opex_location_id": cls.opex_location.id})
        cls.product = cls.env["product.product"].create({"name": "Accounting Test Spare", "type": "product", "standard_price": 75.0})

    def _consume_manual(self, price=75.0):
        self.product.standard_price = price
        order = self.env["repair.order"].create({"legacy_order_type": "repair", "legacy_equipment_id": self.equipment.id, "legacy_workcenter_id": self.workcenter.id, "company_id": self.company.id})
        move = self.env["stock.move"].create({"name": self.product.display_name, "repair_id": order.id, "repair_line_type": "add", "product_id": self.product.id, "product_uom_qty": 1.0, "product_uom": self.product.uom_id.id, "company_id": self.company.id})
        request = self.env["stock.request.order"].browse(order.action_create_legacy_material_request()["res_id"]); line = request.stock_request_ids
        request.action_submit_legacy_finance(); request.action_approve_legacy_finance(); self.env["stock.quant"]._update_available_quantity(self.product, move.location_id, 1.0)
        request.state = "approved"; request.action_reserve_legacy_repair_materials(); move.quantity = 1.0; move.picked = True; order.action_repair_start(); order.action_repair_done()
        return order, request, line

    def test_01_manual_material_posting_is_balanced_and_idempotent(self):
        order, request, line = self._consume_manual()
        move = request.action_post_legacy_materials()
        self.assertEqual(move.state, "posted")
        self.assertEqual(sum(move.line_ids.mapped("balance")), 0.0)
        self.assertEqual(line.legacy_accounting_status, "posted")
        self.assertEqual(request.action_post_legacy_materials(), move)

    def test_02_manual_return_reverses_original_value(self):
        order, request, line = self._consume_manual()
        original = request.action_post_legacy_materials(); line.action_create_legacy_return(); reversal = line.action_post_legacy_return()
        self.assertEqual(reversal.state, "posted")
        self.assertEqual(sum(reversal.line_ids.mapped("debit")), sum(original.line_ids.filtered(lambda item: item.legacy_stock_request_line_id == line).mapped("debit")))
        self.assertEqual(line.action_post_legacy_return(), reversal)

    def test_03_zero_cost_blocks(self):
        order, request, line = self._consume_manual(price=0.0)
        with self.assertRaises(UserError):
            request.action_post_legacy_materials()

    def test_04_labour_reporting_and_posting_modes(self):
        order = self.env["repair.order"].create({"legacy_order_type": "build", "legacy_target_workcenter_id": self.workcenter.id, "legacy_machine_name": "Accounting Build", "company_id": self.company.id})
        operation = self.env["legacy.repair.operation"].create({"repair_order_id": order.id, "name": "Assembly"})
        employee = self.env["hr.employee"].create({"name": "Accounting Worker", "company_id": self.company.id, "legacy_maintenance_hourly_rate": 100.0})
        start = datetime(2026, 1, 1, 8)
        labour = self.env["legacy.repair.labour"].create({"repair_order_id": order.id, "operation_id": operation.id, "employee_id": employee.id, "start_datetime": start, "end_datetime": start + timedelta(hours=2), "manual_adjustment_reason": "Approved build work"})
        labour.action_submit(); labour.action_approve()
        self.company.legacy_labour_posting_mode = "reporting"; self.assertFalse(order.action_post_legacy_labour()); self.assertFalse(labour.journal_entry_id)
        labour.accounting_status = "not_posted"; self.company.legacy_labour_posting_mode = "post_approved"; move = order.action_post_legacy_labour()
        self.assertEqual(move.state, "posted"); self.assertEqual(sum(move.line_ids.mapped("balance")), 0.0); self.assertEqual(labour.journal_entry_id, move)
