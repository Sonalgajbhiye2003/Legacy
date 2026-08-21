from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "legacy_material_request_integration")
class TestMaterialRequestIntegration(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.env.user.write({"groups_id": [(4, cls.env.ref("legacy_maintenance_repair_accounting.group_finance_maintenance_approver").id)]})
        cls.workcenter = cls.env["mrp.workcenter"].create({"name": "MR Test Centre", "company_id": cls.company.id})
        cls.equipment = cls.env["maintenance.equipment"].create({"name": "MR Test Machine", "company_id": cls.company.id, "workcenter_id": cls.workcenter.id})
        cls.product = cls.env["product.product"].create({"name": "MR Test Bearing", "type": "product", "standard_price": 50.0})
        cls.account = cls.env["account.account"].create({"name": "MR Test Expense", "code": "MRTEST01", "account_type": "expense", "company_id": cls.company.id})
        cls.inventory_account = cls.env["account.account"].create({"name": "MR Test Inventory", "code": "MRTEST02", "account_type": "asset_current", "company_id": cls.company.id})
        cls.journal = cls.env["account.journal"].create({"name": "MR Test Journal", "code": "MRTJ", "type": "general", "company_id": cls.company.id})
        cls.capex_location = cls.env["stock.location"].create({"name": "MR Test CAPEX", "usage": "production", "company_id": cls.company.id})
        cls.opex_location = cls.env["stock.location"].create({"name": "MR Test OPEX", "usage": "production", "company_id": cls.company.id})
        cls.company.write({"legacy_cwip_account_id": cls.account.id, "legacy_repair_expense_account_id": cls.account.id, "legacy_inventory_account_id": cls.inventory_account.id, "legacy_material_journal_id": cls.journal.id, "legacy_capex_location_id": cls.capex_location.id, "legacy_opex_location_id": cls.opex_location.id})

    def _order_with_part(self):
        order = self.env["repair.order"].create({"legacy_order_type": "repair", "legacy_equipment_id": self.equipment.id, "legacy_workcenter_id": self.workcenter.id, "company_id": self.company.id})
        move = self.env["stock.move"].create({"name": self.product.display_name, "repair_id": order.id, "repair_line_type": "add", "product_id": self.product.id, "product_uom_qty": 2.0, "product_uom": self.product.uom_id.id, "company_id": self.company.id})
        return order, move

    def test_01_create_requisition_is_idempotent_and_no_duplicate_move(self):
        order, move = self._order_with_part()
        before = self.env["stock.move"].search_count([])
        action = order.action_create_legacy_material_request()
        request = self.env["stock.request.order"].browse(action["res_id"])
        self.assertEqual(len(request.stock_request_ids), 1)
        self.assertEqual(request.stock_request_ids.legacy_repair_move_id, move)
        self.assertEqual(self.env["stock.move"].search_count([]), before)
        order.action_create_legacy_material_request()
        self.assertEqual(self.env["stock.request"].search_count([("legacy_repair_move_id", "=", move.id)]), 1)

    def test_02_finance_approval_assigns_opex_location(self):
        order, move = self._order_with_part(); action = order.action_create_legacy_material_request()
        request = self.env["stock.request.order"].browse(action["res_id"]); line = request.stock_request_ids
        request.action_submit_legacy_finance(); request.action_approve_legacy_finance()
        self.assertEqual(line.legacy_finance_approval_state, "approved")
        self.assertEqual(line.legacy_debit_account_id, self.account)
        self.assertEqual(move.location_dest_id, self.opex_location)
        self.assertEqual(move.legacy_stock_request_line_id, line)

    def test_03_consumption_component_and_return_use_original_move(self):
        order, move = self._order_with_part(); action = order.action_create_legacy_material_request()
        request = self.env["stock.request.order"].browse(action["res_id"]); line = request.stock_request_ids
        request.action_submit_legacy_finance(); request.action_approve_legacy_finance()
        self.env["stock.quant"]._update_available_quantity(self.product, move.location_id, 2.0)
        request.state = "approved"; request.action_reserve_legacy_repair_materials()
        move.quantity = 2.0; move.picked = True
        order.action_repair_start(); order.action_repair_done()
        self.assertEqual(move.state, "done")
        self.assertEqual(len(order.legacy_installed_component_ids), 1)
        return_move = line.action_create_legacy_return()
        self.assertEqual(return_move.origin_returned_move_id, move)
        self.assertEqual(line.legacy_returned_quantity, 2.0)
        self.assertEqual(line.action_create_legacy_return(), return_move)
