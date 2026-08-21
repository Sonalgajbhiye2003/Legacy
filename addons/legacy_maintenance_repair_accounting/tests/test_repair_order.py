from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "legacy_repair_order")
class TestLegacyRepairOrder(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.workcenter = cls.env["mrp.workcenter"].create({"name": "Repair Order Test Centre", "company_id": cls.company.id})
        cls.equipment = cls.env["maintenance.equipment"].create(
            {"name": "Repair Order Test Equipment", "company_id": cls.company.id, "workcenter_id": cls.workcenter.id}
        )

    def test_01_repair_confirmation_validation(self):
        order = self.env["repair.order"].create({"legacy_order_type": "repair", "company_id": self.company.id})
        with self.assertRaises(ValidationError):
            order.action_validate()
        order.write({"legacy_equipment_id": self.equipment.id, "legacy_workcenter_id": self.workcenter.id})
        order.action_validate()
        self.assertEqual(order.state, "confirmed")

    def test_02_build_confirmation_validation(self):
        order = self.env["repair.order"].create({"legacy_order_type": "build", "company_id": self.company.id})
        self.assertEqual(order.legacy_proposed_expense_type, "capex")
        self.assertEqual(order.legacy_capitalization_status, "not_ready")
        with self.assertRaises(ValidationError):
            order.action_validate()
        order.write({"legacy_target_workcenter_id": self.workcenter.id, "legacy_machine_name": "Test Press"})
        order.action_validate()
        self.assertEqual(order.state, "confirmed")

    def test_03_maintenance_type_must_match(self):
        request = self.env["maintenance.request"].create(
            {
                "name": "Build request mismatch",
                "maintenance_for": "workcenter",
                "workcenter_id": self.workcenter.id,
                "legacy_work_type": "build",
                "company_id": self.company.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.env["repair.order"].create(
                {"legacy_order_type": "repair", "legacy_maintenance_request_id": request.id, "company_id": self.company.id}
            )

    def test_04_type_locks_after_confirmation(self):
        order = self.env["repair.order"].create(
            {
                "legacy_order_type": "repair",
                "legacy_equipment_id": self.equipment.id,
                "legacy_workcenter_id": self.workcenter.id,
                "company_id": self.company.id,
            }
        )
        order.action_validate()
        with self.assertRaises(UserError):
            order.write({"legacy_order_type": "build"})

    def test_05_filtered_actions(self):
        repair_action = self.env.ref("legacy_maintenance_repair_accounting.action_legacy_repair_orders")
        build_action = self.env.ref("legacy_maintenance_repair_accounting.action_legacy_build_orders")
        self.assertIn("'repair'", repair_action.domain)
        self.assertIn("'build'", build_action.domain)
