from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "legacy_maintenance_request")
class TestLegacyMaintenanceRequest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.workcenter = cls.env["mrp.workcenter"].create({"name": "Maintenance Test Centre", "company_id": cls.company.id})
        cls.equipment = cls.env["maintenance.equipment"].create(
            {"name": "Maintenance Test Machine", "company_id": cls.company.id, "workcenter_id": cls.workcenter.id}
        )

    def _request_values(self, work_type="repair"):
        return {
            "name": "Test %s request" % work_type,
            "maintenance_for": "workcenter",
            "workcenter_id": self.workcenter.id,
            "legacy_work_type": work_type,
            "legacy_existing_equipment_id": self.equipment.id if work_type == "repair" else False,
            "company_id": self.company.id,
        }

    def test_01_repair_defaults_and_validation(self):
        request = self.env["maintenance.request"].create(self._request_values("repair"))
        self.assertEqual(request.legacy_proposed_expense_type, "opex")
        invalid = self._request_values("repair")
        invalid["legacy_existing_equipment_id"] = False
        with self.assertRaises(ValidationError):
            self.env["maintenance.request"].create(invalid)

    def test_02_build_defaults(self):
        request = self.env["maintenance.request"].create(self._request_values("build"))
        self.assertEqual(request.legacy_proposed_expense_type, "capex")
        self.assertFalse(request.legacy_existing_equipment_id)

    def test_03_create_repair_order_and_duplicate_click(self):
        request = self.env["maintenance.request"].create(self._request_values("repair"))
        first_action = request.action_create_legacy_repair_order()
        order = request.legacy_repair_order_ids
        self.assertEqual(len(order), 1)
        self.assertEqual(order.legacy_order_type, "repair")
        self.assertEqual(order.legacy_equipment_id, self.equipment)
        self.assertEqual(order.legacy_workcenter_id, self.workcenter)
        self.assertEqual(first_action["res_id"], order.id)
        second_action = request.action_create_legacy_repair_order()
        self.assertEqual(second_action["res_id"], order.id)
        self.assertEqual(self.env["repair.order"].search_count([("legacy_maintenance_request_id", "=", request.id)]), 1)

    def test_04_create_build_order(self):
        request = self.env["maintenance.request"].create(self._request_values("build"))
        request.action_create_legacy_repair_order()
        order = request.legacy_repair_order_ids
        self.assertEqual(order.legacy_order_type, "build")
        self.assertEqual(order.legacy_target_workcenter_id, self.workcenter)
        self.assertFalse(order.legacy_equipment_id)

    def test_05_type_locked_after_confirmation(self):
        request = self.env["maintenance.request"].create(self._request_values("repair"))
        request.action_create_legacy_repair_order()
        request.legacy_repair_order_ids.state = "confirmed"
        with self.assertRaises(UserError):
            request.write({"legacy_work_type": "build"})
