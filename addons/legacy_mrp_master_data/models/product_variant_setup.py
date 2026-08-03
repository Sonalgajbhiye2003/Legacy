from odoo import Command, api, models


MODULE = "legacy_mrp_master_data"
COMPANY_XMLID = "base.main_company"
VARIANT_TEMPLATES = [{'xmlid': 'tmpl_pkg_outer_packaging', 'name': 'Outer Packaging', 'attribute': 'Packaging Variant', 'category': 'cat_packaging_materials', 'uom_ref': 'uom.product_uom_unit', 'purchase_ok': True, 'sale_ok': False, 'route_ref': 'purchase_stock.route_warehouse0_buy', 'variants': [{'xmlid': 'prod_outer_packaging_700g', 'value': '700g', 'name': 'Outer Packaging - 700g', 'default_code': 'PKG-OUTER-PACKAGING-700G', 'active': True, 'packaging_enabled': False, 'net_content_qty': None, 'net_content_uom_ref': None, 'bulk_xmlid': None}, {'xmlid': 'prod_outer_packaging_16g', 'value': '16g', 'name': 'Outer Packaging - 16g', 'default_code': 'PKG-OUTER-PACKAGING-16G', 'active': True, 'packaging_enabled': False, 'net_content_qty': None, 'net_content_uom_ref': None, 'bulk_xmlid': None}, {'xmlid': 'prod_outer_packaging_60g', 'value': '60g', 'name': 'Outer Packaging - 60g', 'default_code': 'PKG-OUTER-PACKAGING-60G', 'active': False, 'packaging_enabled': False, 'net_content_qty': None, 'net_content_uom_ref': None, 'bulk_xmlid': None}]}, {'xmlid': 'tmpl_pkg_woven_bag', 'name': 'Woven Bag', 'attribute': 'Packaging Variant', 'category': 'cat_packaging_materials', 'uom_ref': 'uom.product_uom_unit', 'purchase_ok': True, 'sale_ok': False, 'route_ref': 'purchase_stock.route_warehouse0_buy', 'variants': [{'xmlid': 'prod_woven_bag_3kg', 'value': '3kg', 'name': 'Woven Bag - 3kg', 'default_code': 'PKG-WOVEN-BAG-3KG', 'active': True, 'packaging_enabled': False, 'net_content_qty': None, 'net_content_uom_ref': None, 'bulk_xmlid': None}, {'xmlid': 'prod_woven_bag_8kg', 'value': '8kg', 'name': 'Woven Bag - 8kg', 'default_code': 'PKG-WOVEN-BAG-8KG', 'active': True, 'packaging_enabled': False, 'net_content_qty': None, 'net_content_uom_ref': None, 'bulk_xmlid': None}, {'xmlid': 'prod_woven_bag_90g', 'value': '90g', 'name': 'Woven Bag - 90g', 'default_code': 'PKG-WOVEN-BAG-90G', 'active': True, 'packaging_enabled': False, 'net_content_qty': None, 'net_content_uom_ref': None, 'bulk_xmlid': None}, {'xmlid': 'prod_woven_bag_50kg', 'value': '50kg', 'name': 'Woven Bag - 50kg', 'default_code': 'PKG-WOVEN-BAG-50KG', 'active': True, 'packaging_enabled': False, 'net_content_qty': None, 'net_content_uom_ref': None, 'bulk_xmlid': None}, {'xmlid': 'prod_woven_bag_10kg', 'value': '10kg', 'name': 'Woven Bag - 10kg', 'default_code': 'PKG-WOVEN-BAG-10KG', 'active': True, 'packaging_enabled': False, 'net_content_qty': None, 'net_content_uom_ref': None, 'bulk_xmlid': None}]}, {'xmlid': 'tmpl_pkg_puffs_rolls', 'name': 'Puffs Rolls', 'attribute': 'Packaging Variant', 'category': 'cat_packaging_materials', 'uom_ref': 'uom.product_uom_kgm', 'purchase_ok': True, 'sale_ok': False, 'route_ref': 'purchase_stock.route_warehouse0_buy', 'variants': [{'xmlid': 'prod_puffs_rolls_60g', 'value': '60g', 'name': 'Puffs Rolls - 60g', 'default_code': 'PKG-PUFFS-ROLLS-60G', 'active': True, 'packaging_enabled': False, 'net_content_qty': None, 'net_content_uom_ref': None, 'bulk_xmlid': None}, {'xmlid': 'prod_puffs_rolls_16g', 'value': '16g', 'name': 'Puffs Rolls - 16g', 'default_code': 'PKG-PUFFS-ROLLS-16G', 'active': True, 'packaging_enabled': False, 'net_content_qty': None, 'net_content_uom_ref': None, 'bulk_xmlid': None}]}, {'xmlid': 'tmpl_pkg_porridge_outer_box', 'name': 'Porridge Outer Box', 'attribute': 'Packaging Variant', 'category': 'cat_packaging_materials', 'uom_ref': 'uom.product_uom_unit', 'purchase_ok': True, 'sale_ok': False, 'route_ref': 'purchase_stock.route_warehouse0_buy', 'variants': [{'xmlid': 'prod_porridge_outer_box_1_x_20', 'value': '(1 x 20)', 'name': 'Porridge Outer Box (1 x 20)', 'default_code': 'PKG-PORRIDGE-OUTER-BOX-1-X-20', 'active': True, 'packaging_enabled': False, 'net_content_qty': None, 'net_content_uom_ref': None, 'bulk_xmlid': None}, {'xmlid': 'prod_porridge_outer_box_1_x_10', 'value': '(1 x 10)', 'name': 'Porridge Outer Box (1 x 10)', 'default_code': 'PKG-PORRIDGE-OUTER-BOX-1-X-10', 'active': True, 'packaging_enabled': False, 'net_content_qty': None, 'net_content_uom_ref': None, 'bulk_xmlid': None}, {'xmlid': 'prod_porridge_outer_box_1_x_8', 'value': '(1 x 8)', 'name': 'Porridge Outer Box (1 x 8)', 'default_code': 'PKG-PORRIDGE-OUTER-BOX-1-X-8', 'active': True, 'packaging_enabled': False, 'net_content_qty': None, 'net_content_uom_ref': None, 'bulk_xmlid': None}]}, {'xmlid': 'tmpl_pkg_porridge_sachet', 'name': 'Porridge Sachet', 'attribute': 'Packaging Variant', 'category': 'cat_packaging_materials', 'uom_ref': 'uom.product_uom_unit', 'purchase_ok': True, 'sale_ok': False, 'route_ref': 'purchase_stock.route_warehouse0_buy', 'variants': [{'xmlid': 'prod_porridge_sachet_1kg', 'value': '1kg', 'name': 'Porridge Sachet - 1kg', 'default_code': 'PKG-PORRIDGE-SACHET-1KG', 'active': True, 'packaging_enabled': False, 'net_content_qty': None, 'net_content_uom_ref': None, 'bulk_xmlid': None}, {'xmlid': 'prod_porridge_sachet_500g', 'value': '500g', 'name': 'Porridge Sachet - 500g', 'default_code': 'PKG-PORRIDGE-SACHET-500G', 'active': True, 'packaging_enabled': False, 'net_content_qty': None, 'net_content_uom_ref': None, 'bulk_xmlid': None}]}, {'xmlid': 'tmpl_fg_tsp', 'name': 'TSP', 'attribute': 'Pack Variant', 'category': 'cat_finished_goods', 'uom_ref': 'uom.product_uom_unit', 'purchase_ok': False, 'sale_ok': True, 'route_ref': 'mrp.route_warehouse0_manufacture', 'variants': [{'xmlid': 'prod_tsp_3kg_bag', 'value': '3kg Bag', 'name': 'TSP - 3kg Bag', 'default_code': 'FG-TSP-3KG-BAG', 'active': True, 'packaging_enabled': True, 'net_content_qty': 3.0, 'net_content_uom_ref': 'uom.product_uom_kgm', 'bulk_xmlid': 'prod_bulk_tsp'}, {'xmlid': 'prod_tsp_3kg_woven_bag', 'value': '3kg Woven Bag', 'name': 'TSP - 3kg Woven Bag', 'default_code': 'FG-TSP-3KG-WOVEN-BAG', 'active': True, 'packaging_enabled': True, 'net_content_qty': 3.0, 'net_content_uom_ref': 'uom.product_uom_kgm', 'bulk_xmlid': 'prod_bulk_tsp'}, {'xmlid': 'prod_tsp_case_20_x_90g', 'value': 'Case (20 x 90g)', 'name': 'TSP - Case (20 x 90g)', 'default_code': 'FG-TSP-CASE-20-X-90G', 'active': True, 'packaging_enabled': True, 'net_content_qty': 1.8, 'net_content_uom_ref': 'uom.product_uom_kgm', 'bulk_xmlid': 'prod_bulk_tsp'}, {'xmlid': 'prod_tsp_case_10_x_700g', 'value': 'Case (10 x 700g)', 'name': 'TSP - Case (10 x 700g)', 'default_code': 'FG-TSP-CASE-10-X-700G', 'active': True, 'packaging_enabled': True, 'net_content_qty': 7.0, 'net_content_uom_ref': 'uom.product_uom_kgm', 'bulk_xmlid': 'prod_bulk_tsp'}, {'xmlid': 'prod_tsp_case_5_x_700g', 'value': 'Case (5 x 700g)', 'name': 'TSP - Case (5 x 700g)', 'default_code': 'FG-TSP-CASE-5-X-700G', 'active': True, 'packaging_enabled': True, 'net_content_qty': 3.5, 'net_content_uom_ref': 'uom.product_uom_kgm', 'bulk_xmlid': 'prod_bulk_tsp'}, {'xmlid': 'prod_tsp_8kg_woven_bag', 'value': '8kg Woven Bag', 'name': 'TSP - 8kg Woven Bag', 'default_code': 'FG-TSP-8KG-WOVEN-BAG', 'active': True, 'packaging_enabled': True, 'net_content_qty': 8.0, 'net_content_uom_ref': 'uom.product_uom_kgm', 'bulk_xmlid': 'prod_bulk_tsp'}]}, {'xmlid': 'tmpl_fg_corn_puffs', 'name': 'Corn Puffs', 'attribute': 'Pack Variant', 'category': 'cat_finished_goods', 'uom_ref': 'uom.product_uom_unit', 'purchase_ok': False, 'sale_ok': True, 'route_ref': 'mrp.route_warehouse0_manufacture', 'variants': [{'xmlid': 'prod_puffs_case_50_x_16g', 'value': 'Case (50 x 16g)', 'name': 'Puffs - Case (50 x 16g)', 'default_code': 'FG-PUFFS-CASE-50-X-16G', 'active': True, 'packaging_enabled': True, 'net_content_qty': 0.8, 'net_content_uom_ref': 'uom.product_uom_kgm', 'bulk_xmlid': 'prod_corn_puffs'}, {'xmlid': 'prod_puffs_case_30_x_60g', 'value': 'Case (30 x 60g)', 'name': 'Puffs - Case (30 x 60g)', 'default_code': 'FG-PUFFS-CASE-30-X-60G', 'active': True, 'packaging_enabled': True, 'net_content_qty': 1.8, 'net_content_uom_ref': 'uom.product_uom_kgm', 'bulk_xmlid': 'prod_corn_puffs'}, {'xmlid': 'prod_zed_crunch_puffs_case_6_x_22', 'value': 'Zed Crunch Puffs Case (6 X 22)', 'name': 'Zed Crunch Puffs Case (6 X 22)', 'default_code': 'FG-ZED-CRUNCH-PUFFS-CASE-6-X-22', 'active': False, 'packaging_enabled': False, 'net_content_qty': None, 'net_content_uom_ref': None, 'bulk_xmlid': None}]}, {'xmlid': 'tmpl_fg_instant_thobwa', 'name': 'Instant Thobwa', 'attribute': 'Pack Variant', 'category': 'cat_finished_goods', 'uom_ref': 'uom.product_uom_unit', 'purchase_ok': False, 'sale_ok': True, 'route_ref': 'mrp.route_warehouse0_manufacture', 'variants': [{'xmlid': 'prod_instant_thobwa_case_50_x_50g', 'value': 'Case (50 x 50g)', 'name': 'Instant Thobwa - Case (50 x 50g)', 'default_code': 'FG-INSTANT-THOBWA-CASE-50-X-50G', 'active': True, 'packaging_enabled': True, 'net_content_qty': 2.5, 'net_content_uom_ref': 'uom.product_uom_kgm', 'bulk_xmlid': 'prod_bulk_thobwa'}, {'xmlid': 'prod_instant_thobwa_25kg_bag', 'value': '25kg Bag', 'name': 'Instant Thobwa - 25kg Bag', 'default_code': 'FG-INSTANT-THOBWA-25KG-BAG', 'active': True, 'packaging_enabled': True, 'net_content_qty': 25.0, 'net_content_uom_ref': 'uom.product_uom_kgm', 'bulk_xmlid': 'prod_bulk_thobwa'}]}, {'xmlid': 'tmpl_fg_instant_porridge', 'name': 'Instant Porridge', 'attribute': 'Pack Variant', 'category': 'cat_finished_goods', 'uom_ref': 'uom.product_uom_unit', 'purchase_ok': False, 'sale_ok': True, 'route_ref': 'mrp.route_warehouse0_manufacture', 'variants': [{'xmlid': 'prod_instant_porridge_box_8_x_500g', 'value': 'Box (8 x 500g)', 'name': 'Instant Porridge - Box (8 x 500g)', 'default_code': 'FG-INSTANT-PORRIDGE-BOX-8-X-500G', 'active': True, 'packaging_enabled': True, 'net_content_qty': 4.0, 'net_content_uom_ref': 'uom.product_uom_kgm', 'bulk_xmlid': 'prod_bulk_instant_porridge'}, {'xmlid': 'prod_instant_porridge_box_20_x_500g', 'value': 'Box (20 x 500g)', 'name': 'Instant Porridge - Box (20 x 500g)', 'default_code': 'FG-INSTANT-PORRIDGE-BOX-20-X-500G', 'active': True, 'packaging_enabled': True, 'net_content_qty': 10.0, 'net_content_uom_ref': 'uom.product_uom_kgm', 'bulk_xmlid': 'prod_bulk_instant_porridge'}, {'xmlid': 'prod_instant_porridge_10kg_bag', 'value': '10kg Bag', 'name': 'Instant Porridge - 10kg Bag', 'default_code': 'FG-INSTANT-PORRIDGE-10KG-BAG', 'active': True, 'packaging_enabled': True, 'net_content_qty': 10.0, 'net_content_uom_ref': 'uom.product_uom_kgm', 'bulk_xmlid': 'prod_bulk_instant_porridge'}, {'xmlid': 'prod_instant_porridge_50kg_bag', 'value': '50kg Bag', 'name': 'Instant Porridge - 50kg Bag', 'default_code': 'FG-INSTANT-PORRIDGE-50KG-BAG', 'active': True, 'packaging_enabled': True, 'net_content_qty': 50.0, 'net_content_uom_ref': 'uom.product_uom_kgm', 'bulk_xmlid': 'prod_bulk_instant_porridge'}, {'xmlid': 'prod_instant_porridge_box_10_x_1kg', 'value': 'Box (10 x 1kg)', 'name': 'Instant Porridge - Box (10 x 1kg)', 'default_code': 'FG-INSTANT-PORRIDGE-BOX-10-X-1KG', 'active': True, 'packaging_enabled': True, 'net_content_qty': 10.0, 'net_content_uom_ref': 'uom.product_uom_kgm', 'bulk_xmlid': 'prod_bulk_instant_porridge'}]}]


def _xmlid(env, xmlid, record):
    module, name = xmlid.split(".", 1)
    values = {"module": module, "name": name, "model": record._name, "res_id": record.id, "noupdate": True}
    existing = env["ir.model.data"].sudo().search([("module", "=", module), ("name", "=", name)], limit=1)
    if existing:
        existing.write(values)
    else:
        env["ir.model.data"].sudo().create(values)


def _ref(env, xmlid):
    return env.ref(xmlid, raise_if_not_found=False)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def legacy_mrp_ensure_variant_products(self):
        company = _ref(self.env, COMPANY_XMLID) or self.env.company
        attribute_model = self.env["product.attribute"].sudo()
        value_model = self.env["product.attribute.value"].sudo()
        template_model = self.env["product.template"].sudo()
        product_model = self.env["product.product"].sudo().with_context(active_test=False)

        for config in VARIANT_TEMPLATES:
            category = _ref(self.env, MODULE + "." + config["category"])
            uom = _ref(self.env, config["uom_ref"])
            route = _ref(self.env, config["route_ref"]) if config.get("route_ref") else False
            attribute = attribute_model.search([("name", "=", config["attribute"])], limit=1)
            if not attribute:
                attribute = attribute_model.create({"name": config["attribute"], "create_variant": "always"})
            _xmlid(self.env, MODULE + ".attr_" + config["attribute"].lower().replace(" ", "_"), attribute)

            values = []
            for variant_config in config["variants"]:
                value = value_model.search([
                    ("name", "=", variant_config["value"]),
                    ("attribute_id", "=", attribute.id),
                ], limit=1)
                if not value:
                    value = value_model.create({"name": variant_config["value"], "attribute_id": attribute.id})
                _xmlid(self.env, MODULE + ".attr_value_" + variant_config["xmlid"].replace("prod_", ""), value)
                values.append(value.id)

            template = _ref(self.env, MODULE + "." + config["xmlid"])
            if not template:
                template = template_model.search([
                    ("name", "=", config["name"]),
                    ("categ_id", "=", category.id),
                    ("company_id", "in", [False, company.id]),
                ], limit=1)
            template_values = {
                "name": config["name"],
                "detailed_type": "product",
                "categ_id": category.id,
                "uom_id": uom.id,
                "uom_po_id": uom.id,
                "company_id": company.id,
                "sale_ok": config["sale_ok"],
                "purchase_ok": config["purchase_ok"],
            }
            if route:
                template_values["route_ids"] = [Command.set([route.id])]
            if template:
                template.write(template_values)
            else:
                template = template_model.create(template_values)
            _xmlid(self.env, MODULE + "." + config["xmlid"], template)

            line = template.attribute_line_ids.filtered(lambda item: item.attribute_id == attribute)
            if line:
                line.write({"value_ids": [Command.set(values)]})
            else:
                self.env["product.template.attribute.line"].sudo().create({
                    "product_tmpl_id": template.id,
                    "attribute_id": attribute.id,
                    "value_ids": [Command.set(values)],
                })
            template._create_variant_ids()

            for variant_config in config["variants"]:
                product_xmlid = MODULE + "." + variant_config["xmlid"]
                old_product = _ref(self.env, product_xmlid)
                pav = value_model.search([
                    ("name", "=", variant_config["value"]),
                    ("attribute_id", "=", attribute.id),
                ], limit=1)
                ptav = template.attribute_line_ids.product_template_value_ids.filtered(
                    lambda item: item.product_attribute_value_id == pav
                )
                variant = template.with_context(active_test=False).product_variant_ids.filtered(
                    lambda product: ptav and ptav in product.product_template_attribute_value_ids
                )[:1]
                if not variant:
                    continue

                if old_product and old_product != variant:
                    self._legacy_mrp_remap_product_references(old_product, variant)
                    if old_product.product_tmpl_id != template:
                        old_product.product_tmpl_id.write({
                            "active": False,
                            "name": old_product.product_tmpl_id.name + " (archived standalone)",
                        })
                    old_values = {"active": False}
                    if old_product.default_code:
                        archived_code = old_product.default_code
                        if not archived_code.endswith("-ARCHIVED"):
                            archived_code += "-ARCHIVED"
                        old_values["default_code"] = archived_code
                    old_product.write(old_values)

                values_to_write = {
                    "default_code": variant_config["default_code"],
                    "active": variant_config["active"],
                }
                if "packaging_enabled" in variant._fields:
                    values_to_write["packaging_enabled"] = variant_config["packaging_enabled"]
                    if variant_config["packaging_enabled"]:
                        values_to_write.update({
                            "net_content_qty": variant_config["net_content_qty"] or 0.0,
                            "net_content_uom_id": _ref(self.env, variant_config["net_content_uom_ref"]).id if variant_config.get("net_content_uom_ref") else False,
                            "bulk_equivalent_product_id": _ref(self.env, MODULE + "." + variant_config["bulk_xmlid"]).id if variant_config.get("bulk_xmlid") else False,
                        })
                    else:
                        values_to_write.update({
                            "net_content_qty": 0.0,
                            "net_content_uom_id": False,
                            "bulk_equivalent_product_id": False,
                        })
                variant.write(values_to_write)
                _xmlid(self.env, product_xmlid, variant)
        return True

    @api.model
    def _legacy_mrp_remap_product_references(self, old_product, new_product):
        models_fields = [
            ("mrp.packaging.recipe", "product_id"),
            ("mrp.packaging.recipe.line", "packaging_product_id"),
            ("mrp.bom", "product_id"),
            ("mrp.bom.line", "product_id"),
            ("mrp.bom.byproduct", "product_id"),
            ("stock.move", "product_id"),
            ("mrp.production", "product_id"),
        ]
        for model_name, field_name in models_fields:
            if model_name not in self.env:
                continue
            model = self.env[model_name].sudo().with_context(active_test=False)
            if field_name not in model._fields:
                continue
            records = model.search([(field_name, "=", old_product.id)])
            if records:
                records.write({field_name: new_product.id})
