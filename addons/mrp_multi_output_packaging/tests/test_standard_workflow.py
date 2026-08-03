from odoo import Command
from odoo.tests import tagged

from .common import MultiOutputCommon


@tagged("post_install", "-at_install")
class TestStandardWorkflow(MultiOutputCommon):

    def test_standard_mo_remains_native(self):
        final = self.env["product.product"].create({
            "name": "Standard Test Finished Product", "type": "product",
            "uom_id": self.uom_unit.id, "uom_po_id": self.uom_unit.id,
        })
        byproduct = self.env["product.product"].create({
            "name": "Standard Test By-product", "type": "product",
            "uom_id": self.uom_unit.id, "uom_po_id": self.uom_unit.id,
        })
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": final.product_tmpl_id.id,
            "product_id": final.id,
            "product_qty": 1.0,
            "product_uom_id": self.uom_unit.id,
            "manufacturing_workflow": "standard",
            "bom_line_ids": [Command.create({
                "product_id": self.pouch.id, "product_qty": 2.0,
                "product_uom_id": self.uom_unit.id,
            })],
            "byproduct_ids": [Command.create({
                "product_id": byproduct.id, "product_qty": 1.0,
                "product_uom_id": self.uom_unit.id,
            })],
        })
        mo = self.env["mrp.production"].create({
            "product_id": final.id, "product_qty": 1.0,
            "product_uom_id": self.uom_unit.id, "bom_id": bom.id,
        })
        self.assertEqual(mo.manufacturing_workflow, "standard")
        self.assertFalse(mo.output_line_ids)
        self.assertFalse(mo.packaging_line_ids)
        mo.action_confirm()
        self.assertEqual(mo.state, "confirmed")
        self.assertEqual(mo.move_raw_ids.component_source, "process_bom")
        self.assertIn(final, mo.move_finished_ids.product_id)
        self.assertIn(byproduct, mo.move_finished_ids.product_id)
        byproduct_move = mo.move_finished_ids.filtered(lambda move: move.product_id == byproduct)
        self.assertEqual(byproduct_move.expected_byproduct_qty, 1.0)
        self.assertFalse(mo.output_line_ids)
        self.assertFalse(mo.packaging_line_ids)
