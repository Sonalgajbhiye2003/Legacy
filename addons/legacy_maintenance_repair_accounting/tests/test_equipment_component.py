from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "legacy_equipment_component")
class TestEquipmentComponent(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.workcenter = cls.env["mrp.workcenter"].create({"name": "Component Test Centre", "company_id": cls.company.id})
        cls.equipment = cls.env["maintenance.equipment"].create({"name": "Component Test Machine", "company_id": cls.company.id, "workcenter_id": cls.workcenter.id})
        cls.product = cls.env["product.product"].create({"name": "Serial Test Motor", "type": "product", "tracking": "serial"})
        cls.lot = cls.env["stock.lot"].create({"name": "COMP-SERIAL-001", "product_id": cls.product.id, "company_id": cls.company.id})

    def _component(self, name="Motor", **extra):
        values = {
            "name": name,
            "equipment_id": self.equipment.id,
            "product_id": self.product.id,
            "quantity": 1.0,
            "uom_id": self.product.uom_id.id,
            "company_id": self.company.id,
        }
        values.update(extra)
        return self.env["maintenance.equipment.component"].create(values)

    def test_01_manual_creation_has_no_stock_move(self):
        before = self.env["stock.move"].search_count([])
        component = self._component()
        self.assertEqual(component.status, "planned")
        self.assertEqual(self.env["stock.move"].search_count([]), before)

    def test_02_hierarchy_and_recursion(self):
        parent = self._component("Motor")
        child = self._component("Bearing", parent_id=parent.id)
        self.assertEqual(child.parent_id, parent)
        with self.assertRaises(UserError):
            parent.parent_id = child

    def test_03_install_remove_and_history(self):
        component = self._component(lot_id=self.lot.id)
        component.action_install_component()
        component.action_install_component()
        self.assertEqual(component.status, "installed")
        self.assertEqual(len(component.history_ids), 1)
        component.action_remove_component()
        self.assertEqual(component.status, "removed")
        self.assertEqual(len(component.history_ids), 2)

    def test_04_replacement(self):
        old = self._component("Old Motor")
        new = self._component("New Motor")
        old.action_install_component()
        old.action_replace_component(new)
        self.assertEqual(old.status, "removed")
        self.assertEqual(new.status, "installed")

    def test_05_serial_uniqueness(self):
        first = self._component("First", lot_id=self.lot.id)
        first.action_install_component()
        second = self._component("Second", lot_id=self.lot.id)
        with self.assertRaises(ValidationError):
            second.action_install_component()

    def test_06_invalid_transition_and_history_immutable(self):
        component = self._component()
        with self.assertRaises(UserError):
            component.action_remove_component()
        component.action_install_component()
        with self.assertRaises(UserError):
            component.history_ids.unlink()
