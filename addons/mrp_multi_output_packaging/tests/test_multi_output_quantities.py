from odoo import Command
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

    def test_possible_packaged_quantity_uses_main_mo_quantity(self):
        mo = self.create_custom_mo(planned=1000.0)
        output_100 = self.add_output(mo, self.pack_100, self.recipe_100, 137.0)
        output_500 = self.add_output(mo, self.pack_500, self.recipe_500, 83.0)
        output_1000 = self.add_output(mo, self.pack_1000, self.recipe_1000, 29.0)

        self.assertAlmostEqual(output_100.possible_qty_from_mo, 10000.0)
        self.assertAlmostEqual(output_500.possible_qty_from_mo, 2000.0)
        self.assertAlmostEqual(output_1000.possible_qty_from_mo, 1000.0)
        self.assertAlmostEqual(output_100.planned_qty, 137.0)
        self.assertAlmostEqual(output_500.planned_qty, 83.0)

        mo.product_qty = 750.5
        self.assertAlmostEqual(output_100.possible_qty_from_mo, 7505.0)
        self.assertAlmostEqual(output_500.possible_qty_from_mo, 1501.0)
        self.assertAlmostEqual(output_1000.possible_qty_from_mo, 750.0)

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

    def test_confirm_creates_finished_moves_for_packaged_and_remaining_bulk(self):
        mo = self.create_custom_mo(planned=1000.0)
        output_100 = self.add_output(mo, self.pack_100, self.recipe_100, 137.0)
        output_500 = self.add_output(mo, self.pack_500, self.recipe_500, 83.0)

        mo.action_confirm()

        bulk_output = mo.output_line_ids.filtered(
            lambda line: line.output_classification == "primary_bulk"
        )
        self.assertAlmostEqual(bulk_output.planned_qty, 944.8)
        self.assertEqual(output_100.stock_move_id.product_id, self.pack_100)
        self.assertEqual(output_500.stock_move_id.product_id, self.pack_500)
        self.assertEqual(bulk_output.stock_move_id.product_id, self.bulk)
        self.assertAlmostEqual(output_100.stock_move_id.product_uom_qty, 137.0)
        self.assertAlmostEqual(output_500.stock_move_id.product_uom_qty, 83.0)
        self.assertAlmostEqual(bulk_output.stock_move_id.product_uom_qty, 944.8)
        self.assertEqual(
            set(mo.move_finished_ids.product_id.ids),
            {self.bulk.id, self.pack_100.id, self.pack_500.id},
        )

    def test_completion_posts_packaged_and_remaining_bulk_quantities(self):
        mo = self.create_custom_mo(planned=1000.0, actual=1000.0)
        output_100 = self.add_output(mo, self.pack_100, self.recipe_100, 137.0, 137.0)
        output_500 = self.add_output(mo, self.pack_500, self.recipe_500, 83.0, 83.0)
        source = mo.location_src_id
        self.env["stock.quant"]._update_available_quantity(self.process_component, source, 1000.0)
        self.env["stock.quant"]._update_available_quantity(self.pouch, source, 220.0)
        self.env["stock.quant"]._update_available_quantity(self.carton, source, 20.0)

        bulk_before = self.bulk.qty_available
        pack_100_before = self.pack_100.qty_available
        pack_500_before = self.pack_500.qty_available
        mo.action_confirm()
        mo.action_assign()
        if "check_ids" in mo._fields:
            for check in mo.check_ids.filtered(lambda item: item.quality_state == "none"):
                check.do_pass()
        mo.qty_producing = 1000.0
        for move in mo.move_raw_ids:
            move.write({"quantity": move.product_uom_qty, "picked": True})
        result = mo.with_context(skip_consumption=True, skip_backorder=True).button_mark_done()

        self.assertTrue(result)
        self.assertEqual(mo.state, "done")
        self.assertAlmostEqual(output_100.stock_move_id.quantity, 137.0)
        self.assertAlmostEqual(output_500.stock_move_id.quantity, 83.0)
        bulk_output = mo.output_line_ids.filtered(
            lambda line: line.output_classification == "primary_bulk"
        )
        self.assertAlmostEqual(bulk_output.actual_qty, 944.8)
        self.assertAlmostEqual(self.bulk.qty_available - bulk_before, 944.8)
        self.assertAlmostEqual(self.pack_100.qty_available - pack_100_before, 137.0)
        self.assertAlmostEqual(self.pack_500.qty_available - pack_500_before, 83.0)

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

    def test_zero_quantity_variant_does_not_add_packaging_materials(self):
        mo = self.create_custom_mo()
        selected = self.add_output(mo, self.pack_100, self.recipe_100, 25)
        ignored = self.add_output(mo, self.pack_500, self.recipe_500, 0)

        mo.action_confirm()

        self.assertEqual(mo.packaging_line_ids.mapped("output_line_id"), selected)
        self.assertNotIn(ignored, mo.packaging_line_ids.mapped("output_line_id"))

    def test_prepared_draft_removes_packaging_when_variant_is_zeroed(self):
        mo = self.create_custom_mo()
        selected = self.add_output(mo, self.pack_100, self.recipe_100, 25)
        removed = self.add_output(mo, self.pack_500, self.recipe_500, 20)
        mo._prepare_packaging()

        removed.planned_qty = 0

        self.assertEqual(mo.packaging_line_ids.mapped("output_line_id"), selected)
        self.assertNotIn(removed, mo.packaging_line_ids.mapped("output_line_id"))
        self.assertEqual(
            set(mo.recipe_snapshot_ids.mapped("output_line_id").ids),
            {selected.id},
        )

    def test_packaging_variance_uses_displayed_required_quantity(self):
        mo = self.create_custom_mo()
        self.add_output(mo, self.pack_500, self.recipe_500, 25)

        mo.action_confirm()

        pouch_line = mo.packaging_line_ids.filtered(
            lambda line: line.packaging_product_id == self.pouch
        )
        self.assertAlmostEqual(pouch_line.planned_packaging_qty, 25)
        self.assertAlmostEqual(pouch_line.actual_consumed_qty, 0)
        self.assertAlmostEqual(pouch_line.variance_qty, -25)
        self.assertAlmostEqual(pouch_line.variance_percentage, -100)

        pouch_line.actual_consumed_qty = 23
        self.assertAlmostEqual(pouch_line.variance_qty, -2)
        self.assertAlmostEqual(pouch_line.variance_percentage, -8)

    def test_duplicate_starts_with_empty_packaging_execution_review(self):
        workcenter = self.env["mrp.workcenter"].create({
            "name": "Test Duplication Workcenter",
        })
        self.bom.write({
            "operation_ids": [
                Command.create({
                    "name": "Prepare",
                    "sequence": 10,
                    "workcenter_id": workcenter.id,
                    "time_cycle_manual": 1.0,
                }),
                Command.create({
                    "name": "Pack",
                    "sequence": 20,
                    "workcenter_id": workcenter.id,
                    "time_cycle_manual": 1.0,
                }),
            ],
        })
        mo = self.create_custom_mo(planned=1000, actual=900)
        output = self.add_output(mo, self.pack_500, self.recipe_500, 100, 90)
        mo.action_confirm()
        mo.process_loss_qty = 5
        mo.variance_reason = "Previous run"
        packaging_line = mo.packaging_line_ids.filtered(
            lambda line: line.packaging_product_id == self.pouch
        )
        packaging_line.write({
            "actual_consumed_qty": 88,
            "variance_reason": "Previous packaging loss",
        })

        duplicate = mo.copy()

        self.assertEqual(duplicate.state, "draft")
        self.assertAlmostEqual(duplicate.actual_usable_output_qty, 0)
        self.assertAlmostEqual(duplicate.process_loss_qty, 0)
        self.assertFalse(duplicate.variance_reason)
        self.assertFalse(duplicate.variance_approved)
        self.assertTrue(all(line.actual_qty == 0 for line in duplicate.output_line_ids))
        self.assertFalse(duplicate.recipe_snapshot_ids)
        self.assertFalse(duplicate.packaging_line_ids)
        self.assertFalse(duplicate.move_raw_ids.filtered(
            lambda move: move.component_source == "packaging_recipe"
        ))
        self.assertTrue(duplicate.workorder_ids)
        self.assertFalse(duplicate.workorder_ids.blocked_by_workorder_ids)

        duplicate.action_confirm()
        ordered_workorders = duplicate.workorder_ids.sorted(
            key=lambda workorder: (workorder.operation_id.sequence, workorder.id)
        )
        self.assertFalse(ordered_workorders[0].blocked_by_workorder_ids)
        self.assertEqual(
            ordered_workorders[1].blocked_by_workorder_ids,
            ordered_workorders[0],
        )
        self.assertTrue(duplicate.packaging_line_ids)
        self.assertTrue(all(
            line.actual_consumed_qty == 0 for line in duplicate.packaging_line_ids
        ))
        self.assertEqual(
            duplicate.output_line_ids.filtered(
                lambda line: line.product_id == output.product_id
            ).planned_qty,
            output.planned_qty,
        )

    def test_actual_quantity_refreshes_packaging_expectation(self):
        mo = self.create_custom_mo(actual=900)
        output = self.add_output(mo, self.pack_500, self.recipe_500, 1000, 900)
        mo.action_confirm()
        pouch_line = mo.packaging_line_ids.filtered(lambda line: line.packaging_product_id == self.pouch)
        self.assertAlmostEqual(pouch_line.expected_actual_packaging_qty, 900)
        output.actual_qty = 800
        self.assertAlmostEqual(pouch_line.expected_actual_packaging_qty, 800)
