from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "stock_request_approval")
class TestStockRequestApproval(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.uom = cls.env.ref("uom.product_uom_unit")
        cls.product = cls.env["product.product"].create(
            {
                "name": "Approval-only Stock Product",
                "type": "product",
                "uom_id": cls.uom.id,
                "uom_po_id": cls.uom.id,
            }
        )
        request_group = cls.env.ref("stock_request.group_stock_request_user")
        cls.requester = cls.env["res.users"].with_context(
            no_reset_password=True
        ).create(
            {
                "name": "Stock Requester",
                "login": "stock.requester.approval.test",
                "email": "stock.requester@example.com",
                "company_id": cls.company.id,
                "company_ids": [Command.set(cls.company.ids)],
                "groups_id": [Command.set(request_group.ids)],
            }
        )
        cls.approver = cls.env["res.users"].with_context(
            no_reset_password=True
        ).create(
            {
                "name": "Stock Approver",
                "login": "stock.approver.approval.test",
                "email": "stock.approver@example.com",
                "company_id": cls.company.id,
                "company_ids": [Command.set(cls.company.ids)],
                "groups_id": [Command.set(request_group.ids)],
            }
        )

    def setUp(self):
        super().setUp()
        self.env["stock.request.approval.config"].search([]).write(
            {"active": False}
        )

    def _create_matrix(self):
        return self.env["stock.request.approval.config"].create(
            {
                "name": "Default Stock Approval",
                "company_id": self.company.id,
                "level_1_approver_id": self.approver.id,
            }
        )

    def _create_request(self):
        return self.env["stock.request"].with_user(self.requester).create(
            {
                "requested_by": self.requester.id,
                "company_id": self.company.id,
                "warehouse_id": self.warehouse.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "product_id": self.product.id,
                "product_uom_id": self.uom.id,
                "product_uom_qty": 10,
                "request_reason": "Internal approval test",
            }
        )

    def test_approval_does_not_launch_procurement(self):
        self._create_matrix()
        request = self._create_request()

        request.with_user(self.requester).action_request_approval()

        self.assertEqual(request.state, "open")
        self.assertEqual(request.approval_state, "waiting_level_1")
        self.assertEqual(request.current_approver_id, self.approver)
        self.assertFalse(request.move_ids)

        request.with_user(self.approver).action_approve_request()

        self.assertEqual(request.state, "done")
        self.assertEqual(request.approval_state, "approved")
        self.assertFalse(request.move_ids)

    def test_only_configured_approver_can_approve(self):
        self._create_matrix()
        request = self._create_request()
        request.with_user(self.requester).action_request_approval()

        with self.assertRaises(AccessError):
            request.with_user(self.requester).action_approve_request()
