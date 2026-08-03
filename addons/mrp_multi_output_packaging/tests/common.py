from odoo import Command, fields
from odoo.tests.common import TransactionCase


class MultiOutputCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.uom_unit = cls.env.ref("uom.product_uom_unit")
        cls.uom_kg = cls.env.ref("uom.product_uom_kgm")
        cls.bulk = cls.env["product.product"].create({
            "name": "Test Bulk Soya Chunk",
            "type": "product",
            "uom_id": cls.uom_kg.id,
            "uom_po_id": cls.uom_kg.id,
            "company_id": cls.company.id,
        })
        cls.process_component = cls.env["product.product"].create({
            "name": "Test Process Component",
            "type": "product",
            "uom_id": cls.uom_kg.id,
            "uom_po_id": cls.uom_kg.id,
            "company_id": cls.company.id,
        })
        cls.carton = cls.env["product.product"].create({
            "name": "Test Common Carton",
            "type": "product",
            "uom_id": cls.uom_unit.id,
            "uom_po_id": cls.uom_unit.id,
            "company_id": cls.company.id,
        })
        cls.pouch = cls.env["product.product"].create({
            "name": "Test Packaging Pouch",
            "type": "product",
            "uom_id": cls.uom_unit.id,
            "uom_po_id": cls.uom_unit.id,
            "company_id": cls.company.id,
        })
        cls.pack_100 = cls._create_packaged_product("Test Soya Chunk 100 g", 0.1)
        cls.pack_500 = cls._create_packaged_product("Test Soya Chunk 500 g", 0.5)
        cls.pack_1000 = cls._create_packaged_product("Test Soya Chunk 1 kg", 1.0)
        cls.recipe_100 = cls._create_recipe(cls.pack_100, "100G", 0.01)
        cls.recipe_500 = cls._create_recipe(cls.pack_500, "500G", 0.05)
        cls.recipe_1000 = cls._create_recipe(cls.pack_1000, "1KG", 0.10)
        cls.bom = cls.env["mrp.bom"].create({
            "product_tmpl_id": cls.bulk.product_tmpl_id.id,
            "product_id": cls.bulk.id,
            "product_qty": 1000.0,
            "product_uom_id": cls.uom_kg.id,
            "type": "normal",
            "manufacturing_workflow": "custom_multi_output",
            "custom_process_type": "integrated_production_packaging",
            "bom_line_ids": [Command.create({
                "product_id": cls.process_component.id,
                "product_qty": 1000.0,
                "product_uom_id": cls.uom_kg.id,
            })],
        })

    @classmethod
    def _create_packaged_product(cls, name, net_content):
        return cls.env["product.product"].create({
            "name": name,
            "type": "product",
            "uom_id": cls.uom_unit.id,
            "uom_po_id": cls.uom_unit.id,
            "company_id": cls.company.id,
            "packaging_enabled": True,
            "net_content_qty": net_content,
            "net_content_uom_id": cls.uom_kg.id,
            "bulk_equivalent_product_id": cls.bulk.id,
        })

    @classmethod
    def _create_recipe(cls, product, code, carton_qty):
        recipe = cls.env["mrp.packaging.recipe"].create({
            "name": f"Recipe {code}",
            "code": code,
            "product_id": product.id,
            "base_qty": 1.0,
            "base_uom_id": cls.uom_unit.id,
            "company_id": cls.company.id,
            "valid_from": fields.Date.today(),
            "version": "1.0",
            "line_ids": [
                Command.create({
                    "packaging_product_id": cls.pouch.id,
                    "qty_per_base": 1.0,
                    "product_uom_id": cls.uom_unit.id,
                    "rounding_method": "product_uom_rounding",
                }),
                Command.create({
                    "packaging_product_id": cls.carton.id,
                    "qty_per_base": carton_qty,
                    "product_uom_id": cls.uom_unit.id,
                    "rounding_method": "round_up",
                }),
            ],
        })
        product.packaging_recipe_id = recipe
        return recipe

    def create_custom_mo(self, planned=1000.0, actual=0.0):
        mo = self.env["mrp.production"].create({
            "product_id": self.bulk.id,
            "product_qty": planned,
            "product_uom_id": self.uom_kg.id,
            "bom_id": self.bom.id,
            "manufacturing_workflow": "custom_multi_output",
            "custom_process_type": "integrated_production_packaging",
            "bulk_product_id": self.bulk.id,
            "bulk_uom_id": self.uom_kg.id,
            "planned_usable_output_qty": planned,
            "actual_usable_output_qty": actual,
        })
        return mo

    def add_output(self, mo, product, recipe, planned_qty, actual_qty=0.0):
        return self.env["mrp.production.output.line"].create({
            "production_id": mo.id,
            "product_id": product.id,
            "output_classification": "primary_packaged",
            "planned_qty": planned_qty,
            "actual_qty": actual_qty,
            "product_uom_id": self.uom_unit.id,
            "net_content_qty": product.net_content_qty,
            "net_content_uom_id": self.uom_kg.id,
            "bulk_equivalent_product_id": self.bulk.id,
            "packaging_recipe_id": recipe.id,
            "location_dest_id": mo.location_dest_id.id,
        })
