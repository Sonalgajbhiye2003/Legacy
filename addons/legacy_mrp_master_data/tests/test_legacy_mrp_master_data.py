from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestLegacyMrpMasterData(TransactionCase):

    def test_installation_created_no_transactions(self):
        self.assertTrue(self.env.ref("legacy_mrp_master_data.warehouse_legacy_main"))
        self.assertEqual(self.env["mrp.production"].search_count([]), 0)
        self.assertEqual(self.env["stock.move"].search_count([]), 0)
        self.assertEqual(self.env["account.move"].search_count([]), 0)

    def test_product_categories_and_internal_refs(self):
        for xmlid in ["cat_raw_materials", "cat_packaging_materials", "cat_work_in_progress", "cat_by_products", "cat_finished_goods"]:
            self.assertTrue(self.env.ref(f"legacy_mrp_master_data.{xmlid}"))
        product_ids = self.env["ir.model.data"].search([
            ("module", "=", "legacy_mrp_master_data"),
            ("model", "=", "product.product"),
        ]).mapped("res_id")
        products = self.env["product.product"].with_context(active_test=False).browse(product_ids).exists().filtered("default_code")
        codes = products.mapped("default_code")
        self.assertEqual(len(codes), len(set(codes)))
        self.assertTrue(all(code.startswith(("RM-", "PKG-", "WIP-", "BYP-", "FG-")) for code in codes))

    def test_finished_goods_are_configured_as_variants(self):
        expected_templates = {
            "legacy_mrp_master_data.tmpl_fg_tsp": 6,
            "legacy_mrp_master_data.tmpl_fg_instant_porridge": 5,
            "legacy_mrp_master_data.tmpl_fg_instant_thobwa": 2,
            "legacy_mrp_master_data.tmpl_fg_corn_puffs": 3,
        }
        for xmlid, expected_count in expected_templates.items():
            template = self.env.ref(xmlid)
            variants = template.with_context(active_test=False).product_variant_ids
            self.assertEqual(len(variants), expected_count)
            self.assertTrue(template.attribute_line_ids)
            self.assertTrue(all(product.product_template_attribute_value_ids for product in variants))
        for xmlid in [
            "prod_tsp_case_10_x_700g",
            "prod_tsp_8kg_woven_bag",
            "prod_instant_porridge_box_20_x_500g",
            "prod_instant_thobwa_case_50_x_50g",
            "prod_puffs_case_30_x_60g",
        ]:
            product = self.env.ref(f"legacy_mrp_master_data.{xmlid}")
            self.assertGreater(len(product.product_tmpl_id.with_context(active_test=False).product_variant_ids), 1)

    def test_workcenters_and_operations(self):
        expected = {
            "WC-TSP-01 TSP Production Line",
            "WC-THO-01 Instant Thobwa Production Line",
            "WC-POR-01 Instant Porridge Production Line",
            "WC-PUF-01 Corn Puffs Production Line",
        }
        actual = set(self.env["mrp.workcenter"].search([("name", "in", list(expected))]).mapped("name"))
        self.assertEqual(actual, expected)
        for bom in self.env["mrp.bom"].search([("code", "like", "LEGACY-")]):
            sequences = bom.operation_ids.mapped("sequence")
            self.assertEqual(sequences, sorted(sequences))
            self.assertTrue(all(seq % 10 == 0 for seq in sequences))
            self.assertTrue(all(op.workcenter_id for op in bom.operation_ids))

    def test_active_bom_component_validity_and_packaging_source(self):
        packaging_category = self.env.ref("legacy_mrp_master_data.cat_packaging_materials")
        active_boms = self.env["mrp.bom"].search([("code", "like", "LEGACY-"), ("active", "=", True)])
        self.assertTrue(active_boms)
        for bom in active_boms:
            self.assertGreater(bom.product_qty, 0)
            self.assertEqual(bom.manufacturing_workflow, "custom_multi_output")
            self.assertEqual(bom.custom_process_type, "integrated_production_packaging")
            for line in bom.bom_line_ids:
                self.assertGreater(line.product_qty, 0)
                self.assertNotEqual(line.product_id.categ_id, packaging_category)
                self.assertEqual(line.product_uom_id.category_id, line.product_id.uom_id.category_id)

    def test_packaging_recipes_are_single_packaging_source(self):
        recipes = self.env["mrp.packaging.recipe"].search([("code", "like", "PR-")])
        self.assertTrue(recipes)
        for recipe in recipes:
            self.assertGreater(recipe.base_qty, 0)
            self.assertEqual(recipe.base_uom_id.category_id, recipe.product_id.uom_id.category_id)
            seen = set()
            for line in recipe.line_ids:
                self.assertGreater(line.qty_per_base, 0)
                key = (line.packaging_product_id.id, line.product_uom_id.id, line.operation_id.id)
                self.assertNotIn(key, seen)
                seen.add(key)
                self.assertEqual(line.product_uom_id.category_id, line.packaging_product_id.uom_id.category_id)

    def test_every_packaging_enabled_variant_has_an_active_default_recipe(self):
        products = self.env["product.product"].search([("packaging_enabled", "=", True)])
        self.assertTrue(products)
        for product in products:
            recipe = product.packaging_recipe_id
            self.assertTrue(recipe, f"Missing default packaging recipe for {product.display_name}")
            self.assertTrue(recipe.active, f"Inactive packaging recipe for {product.display_name}")
            self.assertEqual(recipe.product_id, product)
            self.assertTrue(recipe.line_ids, f"Packaging recipe has no materials for {product.display_name}")

    def test_inactive_boms_exist_for_unresolved_sources(self):
        inactive_boms = self.env["mrp.bom"].with_context(active_test=False).search([
            ("code", "like", "LEGACY-"), ("active", "=", False)
        ])
        self.assertTrue(inactive_boms)
