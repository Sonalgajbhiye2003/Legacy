from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestSoyaChunksSingleBom(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bom = cls.env.ref("legacy_mrp_master_data.bom_soya_chunks_single_process")
        cls.bulk = cls.env.ref("legacy_mrp_master_data.prod_bulk_tsp")
        cls.soya_beans = cls.env.ref("legacy_mrp_master_data.prod_soya_beans")
        cls.soya_oil = cls.env.ref("legacy_mrp_master_data.prod_crude_oil")
        cls.low_fat_cake = cls.env.ref("legacy_mrp_master_data.prod_low_fat_cake")
        cls.uom_kg = cls.env.ref("uom.product_uom_kgm")

    def test_master_mapping_and_safe_inactive_state(self):
        self.assertEqual(self.bulk.default_code, "WIP-BULK-TSP")
        self.assertEqual(self.soya_beans.default_code, "RM-SOYA-BEANS")
        self.assertEqual(self.soya_oil.default_code, "BYP-CRUDE-OIL")
        self.assertEqual(self.low_fat_cake.default_code, "BYP-LOW-FAT-CAKE")
        self.assertEqual(self.bulk.uom_id, self.uom_kg)
        self.assertEqual(self.soya_beans.uom_id, self.uom_kg)
        self.assertEqual(self.soya_oil.uom_id, self.uom_kg)
        self.assertFalse(self.bom.active)
        self.assertEqual(self.bom.manufacturing_workflow, "standard")
        self.assertEqual(self.bom.company_id, self.env.company)
        self.assertEqual(self.bom.operation_ids.company_id, self.env.company)

    def test_no_duplicate_critical_product_or_processing_bom(self):
        for code in (
            "RM-SOYA-BEANS",
            "WIP-BULK-TSP",
            "BYP-CRUDE-OIL",
            "BYP-LOW-FAT-CAKE",
        ):
            self.assertEqual(
                self.env["product.product"].with_context(active_test=False).search_count([
                    ("default_code", "=", code),
                ]),
                1,
            )
        self.assertEqual(
            self.env["mrp.bom"].with_context(active_test=False).search_count([
                ("code", "=", "LEGACY-SOYA-CHUNKS-SINGLE-PROCESS"),
            ]),
            1,
        )

    def test_unapproved_quantities_are_not_installed_as_zero_lines(self):
        self.assertFalse(self.bom.bom_line_ids)
        self.assertFalse(self.bom.byproduct_ids)

    def test_processing_operations_are_ordered_and_exclude_packaging(self):
        expected = [
            (10, "Soya Bean Receipt / Preparation"),
            (20, "Soya Bean Cleaning"),
            (30, "Soya Bean Milling"),
            (40, "First Extrusion"),
            (50, "Oil Extraction"),
            (60, "Low-Fat Cake Milling"),
            (70, "Second Extrusion"),
            (80, "Grading"),
            (90, "Final Quality Release"),
        ]
        self.assertEqual(
            [(op.sequence, op.name) for op in self.bom.operation_ids], expected
        )
        self.assertFalse(self.bom.operation_ids.filtered(
            lambda op: "pack" in op.name.lower()
        ))

    def test_source_consistent_tsp_boms_are_visible_and_review_boms_archived(self):
        pack_boms = self.env["mrp.bom"].with_context(active_test=False).search([
            ("code", "like", "LEGACY-TSP-%"),
        ])
        self.assertEqual(len(pack_boms), 6)
        self.assertEqual(
            set(pack_boms.filtered("active").mapped("code")),
            {"LEGACY-TSP-CASE-10-X-700G", "LEGACY-TSP-8KG-WOVEN-BAG"},
        )
        self.assertEqual(len(pack_boms.filtered(lambda bom: not bom.active)), 4)

    def test_tsp_packaging_remains_in_recipe_layer(self):
        variants = self.env["product.product"].search([
            ("bulk_equivalent_product_id", "=", self.bulk.id),
            ("packaging_enabled", "=", True),
        ])
        self.assertTrue(variants)
        self.assertTrue(all(product.packaging_recipe_id for product in variants))

    def _create_synthetic_standard_mo(self, quantity):
        # Synthetic test data proves native Odoo behavior only; these quantities
        # are never installed as Legacy master data.
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": self.bulk.product_tmpl_id.id,
            "product_id": self.bulk.id,
            "product_qty": 90.0,
            "product_uom_id": self.uom_kg.id,
            "manufacturing_workflow": "standard",
            "bom_line_ids": [Command.create({
                "product_id": self.soya_beans.id,
                "product_qty": 100.0,
                "product_uom_id": self.uom_kg.id,
            })],
            "byproduct_ids": [Command.create({
                "product_id": self.soya_oil.id,
                "product_qty": 10.0,
                "product_uom_id": self.uom_kg.id,
                "cost_share": 10.0,
            })],
        })
        mo = self.env["mrp.production"].create({
            "product_id": self.bulk.id,
            "product_qty": quantity,
            "product_uom_id": self.uom_kg.id,
            "bom_id": bom.id,
        })
        mo.action_confirm()
        return mo

    def test_native_standard_mo_can_carry_main_and_byproduct(self):
        mo = self._create_synthetic_standard_mo(90.0)
        self.assertEqual(mo.state, "confirmed")
        self.assertIn(self.bulk, mo.move_finished_ids.product_id)
        self.assertIn(self.soya_oil, mo.move_finished_ids.product_id)
        oil_move = mo.move_finished_ids.filtered(
            lambda move: move.product_id == self.soya_oil
        )
        self.assertEqual(len(oil_move), 1)
        self.assertEqual(oil_move.expected_byproduct_qty, 10.0)
        self.assertFalse(mo.output_line_ids)
        self.assertFalse(mo.packaging_line_ids)

    def test_native_byproduct_scales_once_for_partial_planned_quantity(self):
        mo = self._create_synthetic_standard_mo(45.0)
        oil_moves = mo.move_finished_ids.filtered(
            lambda move: move.product_id == self.soya_oil
        )
        self.assertEqual(len(oil_moves), 1)
        self.assertEqual(oil_moves.expected_byproduct_qty, 5.0)

    def test_cancelling_standard_mo_cancels_both_output_moves(self):
        mo = self._create_synthetic_standard_mo(90.0)
        mo.action_cancel()
        self.assertEqual(mo.state, "cancel")
        self.assertTrue(all(move.state == "cancel" for move in mo.move_finished_ids))
