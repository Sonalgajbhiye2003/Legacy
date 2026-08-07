from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestConsolidatedProcessBoms(TransactionCase):

    def _component_quantities(self, bom):
        return {
            line.product_id.default_code: line.product_qty
            for line in bom.bom_line_ids
        }

    def test_exactly_three_active_consolidated_process_boms(self):
        codes = {
            "LEGACY-SOYA-CHUNKS-SINGLE-PROCESS",
            "LEGACY-INSTANT-THOBWA-SINGLE-PROCESS",
            "LEGACY-CORN-PUFFS-SINGLE-PROCESS",
        }
        boms = self.env["mrp.bom"].search([("code", "in", list(codes))])
        self.assertEqual(set(boms.mapped("code")), codes)
        self.assertTrue(all(bom.active for bom in boms))
        self.assertTrue(all(bom.product_qty == 1.0 for bom in boms))
        self.assertTrue(all(bom.manufacturing_workflow == "custom_multi_output" for bom in boms))

    def test_thobwa_normalized_recipe_and_variants(self):
        bom = self.env.ref("legacy_mrp_master_data.bom_instant_thobwa_single_process")
        expected = {
            "RM-MAIZE": 0.7854545454545455,
            "RM-SOYA-BEANS": 0.07636363636363637,
            "RM-SUGAR": 0.13636363636363635,
            "RM-SALT": 0.01,
            "RM-SWEETENER": 0.0007727272727272728,
        }
        actual = self._component_quantities(bom)
        self.assertEqual(set(actual), set(expected))
        for code, quantity in expected.items():
            self.assertAlmostEqual(actual[code], quantity, places=4)

        template = self.env.ref("legacy_mrp_master_data.tmpl_fg_instant_thobwa")
        active_variants = template.product_variant_ids.filtered("active")
        self.assertEqual(len(active_variants), 2)
        self.assertTrue(all(product.bulk_equivalent_product_id == bom.product_id for product in active_variants))
        self.assertTrue(all(product.packaging_recipe_id.active for product in active_variants))

    def test_puffs_normalized_recipe_and_variants(self):
        bom = self.env.ref("legacy_mrp_master_data.bom_corn_puffs_single_process")
        expected = {
            "RM-BREAKFAST-MEAL": 0.9057971014492754,
            "RM-SUNSET-YELLOW": 0.001811594202898551,
            "RM-SALT": 0.006014492753623188,
            "RM-CALCIUM-CARBONATE": 0.0009057971014492754,
            "RM-BAKING-POWDER": 0.001811594202898551,
            "RM-COOKING-OIL": 0.06521739130434783,
            "RM-CHEESE-SPICE": 0.02028985507246377,
        }
        actual = self._component_quantities(bom)
        self.assertEqual(set(actual), set(expected))
        for code, quantity in expected.items():
            self.assertAlmostEqual(actual[code], quantity, places=4)

        template = self.env.ref("legacy_mrp_master_data.tmpl_fg_corn_puffs")
        active_variants = template.product_variant_ids.filtered("active")
        self.assertEqual(len(active_variants), 2)
        self.assertTrue(all(product.bulk_equivalent_product_id == bom.product_id for product in active_variants))
        self.assertTrue(all(product.packaging_recipe_id.active for product in active_variants))

    def test_packaging_recipes_use_consolidated_packaging_operations(self):
        mappings = {
            "tmpl_fg_tsp": "op_soya_chunks_100_packaging",
            "tmpl_fg_instant_thobwa": "op_thobwa_single_packaging",
            "tmpl_fg_corn_puffs": "op_puffs_single_packaging",
        }
        for template_xmlid, operation_xmlid in mappings.items():
            template = self.env.ref(f"legacy_mrp_master_data.{template_xmlid}")
            operation = self.env.ref(f"legacy_mrp_master_data.{operation_xmlid}")
            variants = template.product_variant_ids.filtered(lambda product: product.active and product.packaging_enabled)
            self.assertTrue(variants)
            for product in variants:
                self.assertEqual(product.default_packaging_operation_id, operation)
                self.assertEqual(product.packaging_recipe_id.operation_id, operation)
                self.assertTrue(all(line.operation_id == operation for line in product.packaging_recipe_id.line_ids))

    def test_legacy_pack_specific_boms_are_archived(self):
        old_codes = [
            "LEGACY-INSTANT-THOBWA-CASE-50-X-50G",
            "LEGACY-INSTANT-THOBWA-25KG-BAG",
            "LEGACY-PUFFS-CASE-50-X-16G",
            "LEGACY-PUFFS-CASE-30-X-60G",
            "LEGACY-ZED-CRUNCH-PUFFS-CASE-6-X-22",
        ]
        boms = self.env["mrp.bom"].with_context(active_test=False).search([("code", "in", old_codes)])
        self.assertEqual(set(boms.mapped("code")), set(old_codes))
        self.assertFalse(boms.filtered("active"))
