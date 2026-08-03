from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import MultiOutputCommon


@tagged("post_install", "-at_install")
class TestPackagingRecipe(MultiOutputCommon):

    def test_effective_date_and_overlap(self):
        self.assertEqual(
            self.env["mrp.packaging.recipe"].effective_recipe(self.pack_100, self.company),
            self.recipe_100,
        )
        with self.assertRaises(ValidationError):
            self.env["mrp.packaging.recipe"].create({
                "name": "Overlapping Recipe",
                "product_id": self.pack_100.id,
                "base_qty": 1,
                "base_uom_id": self.uom_unit.id,
                "company_id": self.company.id,
                "valid_from": fields.Date.today(),
                "version": "2.0",
            })

    def test_rounding_and_wastage(self):
        calc = self.env["mrp.production.packaging.line"]
        self.assertEqual(calc.calculate_requirement(1000, 0.05, 0, "round_up", self.uom_unit), 50)
        self.assertEqual(calc.calculate_requirement(10, 1, 10, "no_rounding", self.uom_unit), 11)
        self.assertEqual(calc.calculate_requirement(3, 0.4, 0, "round_nearest", self.uom_unit), 1)

    def test_snapshot_is_immutable(self):
        mo = self.create_custom_mo()
        self.add_output(mo, self.pack_100, self.recipe_100, 100)
        mo.action_confirm()
        snapshot_qty = mo.recipe_snapshot_ids.line_ids.filtered(
            lambda line: line.packaging_product_id == self.pouch
        ).qty_per_unit
        self.recipe_100.line_ids.filtered(lambda line: line.packaging_product_id == self.pouch).qty_per_base = 2
        self.assertEqual(snapshot_qty, 1)
        self.assertEqual(
            mo.recipe_snapshot_ids.line_ids.filtered(lambda line: line.packaging_product_id == self.pouch).qty_per_unit,
            1,
        )

    def test_company_record_rule(self):
        other_company = self.env["res.company"].create({
            "name": "Multi Output Other Company", "sequence_prefix": "MOT",
        })
        user = self.env["res.users"].create({
            "name": "Multi Output Rule User",
            "login": "multi.output.rule.user",
            "company_id": self.company.id,
            "company_ids": [Command.set([self.company.id])],
            "groups_id": [Command.set([self.env.ref("mrp_multi_output_packaging.group_multi_output_user").id])],
        })
        foreign_product = self.env["product.product"].create({
            "name": "Foreign Packaged Product", "type": "product",
            "uom_id": self.uom_unit.id, "uom_po_id": self.uom_unit.id,
            "company_id": other_company.id,
        })
        foreign_recipe = self.env["mrp.packaging.recipe"].create({
            "name": "Foreign Recipe", "product_id": foreign_product.id,
            "base_qty": 1.0, "base_uom_id": self.uom_unit.id,
            "company_id": other_company.id, "valid_from": fields.Date.today(),
            "version": "1.0",
        })
        visible = self.env["mrp.packaging.recipe"].with_user(user).search([("id", "=", foreign_recipe.id)])
        self.assertFalse(visible)
        self.assertTrue(self.env["mrp.packaging.recipe"].with_user(user).check_access_rights("read", raise_exception=False))
