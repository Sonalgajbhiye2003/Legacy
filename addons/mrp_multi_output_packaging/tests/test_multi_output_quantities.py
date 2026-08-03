from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import MultiOutputCommon


@tagged("post_install", "-at_install")
class TestMultiOutputQuantities(MultiOutputCommon):

    def test_bom_default_creates_packaged_output_automatically(self):
        self.bom.default_packaged_product_id = self.pack_500

        mo = self.create_custom_mo(planned=1000.0)
        packaged = mo.output_line_ids.filtered(
            lambda line: line.output_classification == "primary_packaged"
        )

        self.assertEqual(len(packaged), 1)
        self.assertEqual(packaged.product_id, self.pack_500)
        self.assertAlmostEqual(packaged.planned_qty, 2000.0)
        self.assertEqual(packaged.packaging_recipe_id, self.recipe_500)

    def test_confirm_repairs_existing_mo_after_bom_default_is_configured(self):
        mo = self.create_custom_mo(planned=1000.0)
        self.assertFalse(
            mo.output_line_ids.filtered(
                lambda line: line.output_classification == "primary_packaged"
            )
        )
        self.bom.default_packaged_product_id = self.pack_500

        mo.action_confirm()

        packaged = mo.output_line_ids.filtered(
            lambda line: line.output_classification == "primary_packaged"
        )
        self.assertEqual(packaged.product_id, self.pack_500)
        self.assertAlmostEqual(packaged.planned_qty, 2000.0)

    def test_bulk_product_onchange_does_not_create_orphan_output(self):
        mo = self.env["mrp.production"].new({
            "product_id": self.bulk.id,
            "product_qty": 1000.0,
            "product_uom_id": self.uom_kg.id,
            "bom_id": self.bom.id,
            "manufacturing_workflow": "custom_multi_output",
            "custom_process_type": "integrated_production_packaging",
            "bulk_product_id": self.bulk.id,
            "bulk_uom_id": self.uom_kg.id,
            "planned_usable_output_qty": 1000.0,
        })

        mo._onchange_sync_bulk_line()

        self.assertFalse(mo.output_line_ids)

    def test_saved_mo_creates_primary_bulk_output(self):
        mo = self.create_custom_mo()
        bulk_line = mo.output_line_ids.filtered(
            lambda line: line.output_classification == "primary_bulk"
        )

        self.assertEqual(len(bulk_line), 1)
        self.assertEqual(bulk_line.production_id, mo)
        self.assertEqual(bulk_line.product_id, self.bulk)

    def test_confirm_prepares_packaging_without_manual_action(self):
        mo = self.create_custom_mo()
        self.add_output(mo, self.pack_100, self.recipe_100, 100)

        self.assertFalse(mo.recipe_snapshot_ids)
        self.assertFalse(mo.packaging_line_ids)
        self.assertFalse(mo.move_raw_ids.filtered(lambda move: move.component_source == "packaging_recipe"))

        mo.action_confirm()

        self.assertTrue(mo.recipe_snapshot_ids)
        self.assertTrue(mo.packaging_line_ids)
        self.assertTrue(mo.move_raw_ids.filtered(lambda move: move.component_source == "packaging_recipe"))

    def test_duplicate_output_is_rejected(self):
        mo = self.create_custom_mo()
        self.add_output(mo, self.pack_100, self.recipe_100, 10)
        with self.assertRaises(ValidationError):
            self.add_output(mo, self.pack_100, self.recipe_100, 20)

    def test_packaging_snapshot_calculation_and_consolidation(self):
        mo = self.create_custom_mo()
        self.add_output(mo, self.pack_100, self.recipe_100, 2000)
        self.add_output(mo, self.pack_500, self.recipe_500, 1000)
        self.add_output(mo, self.pack_1000, self.recipe_1000, 100)
        mo.action_confirm()
        self.assertEqual(len(mo.recipe_snapshot_ids), 3)
        self.assertEqual(len(mo.packaging_line_ids), 6)
        packaging_moves = mo.move_raw_ids.filtered(lambda move: move.component_source == "packaging_recipe")
        self.assertEqual(len(packaging_moves), 2)
        carton_move = packaging_moves.filtered(lambda move: move.product_id == self.carton)
        self.assertEqual(carton_move.product_uom_qty, 80)
        self.assertEqual(len(carton_move.packaging_line_ids), 3)
        self.assertTrue(all(move.component_source == "process_bom" for move in mo.move_raw_ids.filtered("bom_line_id")))

    def test_actual_quantity_refreshes_packaging_expectation(self):
        mo = self.create_custom_mo(actual=900)
        output = self.add_output(mo, self.pack_500, self.recipe_500, 1000, 900)
        mo.action_confirm()
        pouch_line = mo.packaging_line_ids.filtered(lambda line: line.packaging_product_id == self.pouch)
        self.assertAlmostEqual(pouch_line.expected_actual_packaging_qty, 900)
        output.actual_qty = 800
        self.assertAlmostEqual(pouch_line.expected_actual_packaging_qty, 800)
