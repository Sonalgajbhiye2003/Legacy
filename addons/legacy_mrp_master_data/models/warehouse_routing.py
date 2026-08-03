from odoo import Command, api, models

from ..hooks import _ensure_location, _ensure_xmlid


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    @api.model
    def configure_legacy_storage_routes(self):
        """Create idempotent category storage push/pull flows for LMWH."""
        warehouse = self.env.ref(
            "legacy_mrp_master_data.warehouse_legacy_main",
            raise_if_not_found=False,
        )
        if not warehouse:
            return True

        stock = warehouse.lot_stock_id
        production = self.env["stock.location"].search([
            ("usage", "=", "production"),
            ("company_id", "in", [False, warehouse.company_id.id]),
        ], limit=1)
        customers = self.env.ref("stock.stock_location_customers")
        internal_type = warehouse.int_type_id
        manufacturing_type = warehouse.manu_type_id
        delivery_type = warehouse.out_type_id

        raw_location = _ensure_location(
            self.env, "loc_legacy_stock_raw_materials", "Raw Materials", "internal", stock
        )
        packaging_location = _ensure_location(
            self.env, "loc_legacy_stock_packaging_materials", "Packaging Materials", "internal", stock
        )
        finished_location = _ensure_location(
            self.env, "loc_legacy_stock_finished_goods", "Finished Goods", "internal", stock
        )
        spares_location = _ensure_location(
            self.env, "loc_legacy_stock_spares", "Spares", "internal", stock
        )

        route_definitions = [
            (
                "route_legacy_raw_materials_storage",
                "LMWH Raw Materials Storage",
                [self.env.ref("legacy_mrp_master_data.cat_raw_materials")],
                [
                    ("rule_legacy_raw_materials_push", "Put Away Raw Materials", "push", stock, raw_location, internal_type, "transparent"),
                    ("rule_legacy_raw_materials_pull", "Pull Raw Materials to Production", "pull", raw_location, production, manufacturing_type, "manual"),
                ],
            ),
            (
                "route_legacy_packaging_storage",
                "LMWH Packaging Materials Storage",
                [self.env.ref("legacy_mrp_master_data.cat_packaging_materials")],
                [
                    ("rule_legacy_packaging_push", "Put Away Packaging Materials", "push", stock, packaging_location, internal_type, "transparent"),
                    ("rule_legacy_packaging_pull", "Pull Packaging to Production", "pull", packaging_location, production, manufacturing_type, "manual"),
                ],
            ),
            (
                "route_legacy_spares_storage",
                "LMWH Spares Storage",
                [self.env.ref("legacy_mrp_master_data.cat_spares")],
                [
                    ("rule_legacy_spares_push", "Put Away Spares", "push", stock, spares_location, internal_type, "transparent"),
                    ("rule_legacy_spares_pull", "Pull Spares to Production", "pull", spares_location, production, internal_type, "manual"),
                ],
            ),
            (
                "route_legacy_finished_goods_storage",
                "LMWH Produced Goods Storage",
                [
                    self.env.ref("legacy_mrp_master_data.cat_finished_goods"),
                    self.env.ref("legacy_mrp_master_data.cat_work_in_progress"),
                ],
                [
                    ("rule_legacy_finished_goods_push", "Put Away Produced Goods", "push", stock, finished_location, internal_type, "transparent"),
                    ("rule_legacy_finished_goods_pull", "Pull Finished Goods for Delivery", "pull", finished_location, customers, delivery_type, "manual"),
                ],
            ),
        ]

        Route = self.env["stock.route"].sudo()
        Rule = self.env["stock.rule"].sudo()
        for route_xmlid, route_name, categories, rules in route_definitions:
            route = self.env.ref(
                f"legacy_mrp_master_data.{route_xmlid}", raise_if_not_found=False
            )
            route_values = {
                "name": route_name,
                "company_id": warehouse.company_id.id,
                "product_categ_selectable": True,
                "warehouse_ids": [Command.set([warehouse.id])],
                "categ_ids": [Command.set([category.id for category in categories])],
            }
            if route:
                route.write(route_values)
            else:
                route = Route.create(route_values)
                _ensure_xmlid(self.env, f"legacy_mrp_master_data.{route_xmlid}", route)

            for rule_xmlid, rule_name, action, source, destination, picking_type, auto in rules:
                rule = self.env.ref(
                    f"legacy_mrp_master_data.{rule_xmlid}", raise_if_not_found=False
                )
                rule_values = {
                    "name": rule_name,
                    "route_id": route.id,
                    "action": action,
                    "location_src_id": source.id,
                    "location_dest_id": destination.id,
                    "picking_type_id": picking_type.id,
                    "procure_method": "make_to_stock",
                    "auto": auto,
                    "warehouse_id": warehouse.id,
                    "company_id": warehouse.company_id.id,
                }
                if rule:
                    rule.write(rule_values)
                else:
                    rule = Rule.create(rule_values)
                    _ensure_xmlid(self.env, f"legacy_mrp_master_data.{rule_xmlid}", rule)
        return True
