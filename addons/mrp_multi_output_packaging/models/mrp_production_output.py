from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_round

from .mrp_packaging_recipe import ROUNDING_SELECTION


OUTPUT_CLASSIFICATION = [
    ("primary_packaged", "Primary Packaged"),
    ("primary_bulk", "Primary Bulk"),
]


class MrpProductionOutputLine(models.Model):
    _name = "mrp.production.output.line"
    _description = "Manufacturing Finished Output Plan"
    _order = "sequence, id"
    _check_company_auto = True

    production_id = fields.Many2one("mrp.production", required=True, ondelete="cascade", index=True, check_company=True)
    company_id = fields.Many2one(related="production_id.company_id", store=True, index=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one("product.product", required=True, check_company=True)
    output_classification = fields.Selection(OUTPUT_CLASSIFICATION, required=True, default="primary_packaged")
    planned_qty = fields.Float(digits="Product Unit of Measure")
    actual_qty = fields.Float(digits="Product Unit of Measure", copy=False)
    product_uom_id = fields.Many2one("uom.uom", required=True)
    net_content_qty = fields.Float(digits="Product Unit of Measure")
    net_content_uom_id = fields.Many2one("uom.uom")
    bulk_equivalent_product_id = fields.Many2one("product.product", check_company=True)
    equivalent_bulk_qty = fields.Float(
        compute="_compute_equivalent_bulk_qty", store=True, digits="Product Unit of Measure"
    )
    possible_qty_from_mo = fields.Float(
        string="Possible from MO Qty",
        compute="_compute_possible_qty_from_mo",
        store=True,
        digits="Product Unit of Measure",
        help=(
            "Maximum packaged units if the MO's entire main quantity is packed "
            "into this variant. This is a planning guide and does not change the "
            "Quantity to Produce."
        ),
    )
    packaging_recipe_id = fields.Many2one("mrp.packaging.recipe", check_company=True)
    packaging_recipe_version = fields.Char(readonly=True)
    lot_id = fields.Many2one("stock.lot", check_company=True, copy=False)
    location_dest_id = fields.Many2one("stock.location", check_company=True)
    stock_move_id = fields.Many2one("stock.move", readonly=True, copy=False, check_company=True)
    state = fields.Selection(related="production_id.state", store=True)
    notes = fields.Text()

    @api.depends(
        "planned_qty", "actual_qty", "net_content_qty", "net_content_uom_id",
        "bulk_equivalent_product_id", "output_classification"
    )
    def _compute_equivalent_bulk_qty(self):
        for line in self:
            line.equivalent_bulk_qty = 0.0
            if line.output_classification != "primary_packaged" or not line.net_content_uom_id or not line.bulk_equivalent_product_id:
                continue
            quantity = line.actual_qty if line.actual_qty else line.planned_qty
            content = quantity * line.net_content_qty
            bulk_uom = line.bulk_equivalent_product_id.uom_id
            if line.net_content_uom_id.category_id == bulk_uom.category_id:
                line.equivalent_bulk_qty = line.net_content_uom_id._compute_quantity(content, bulk_uom)

    @api.depends(
        "production_id.product_qty",
        "production_id.product_uom_id",
        "net_content_qty",
        "net_content_uom_id",
        "product_uom_id",
        "output_classification",
    )
    def _compute_possible_qty_from_mo(self):
        for line in self:
            line.possible_qty_from_mo = 0.0
            production = line.production_id
            if (
                line.output_classification != "primary_packaged"
                or not production.product_uom_id
                or not line.net_content_uom_id
                or line.net_content_qty <= 0
                or production.product_uom_id.category_id != line.net_content_uom_id.category_id
            ):
                continue
            main_qty_in_content_uom = production.product_uom_id._compute_quantity(
                production.product_qty,
                line.net_content_uom_id,
                round=False,
            )
            possible_qty = main_qty_in_content_uom / line.net_content_qty
            line.possible_qty_from_mo = float_round(
                possible_qty,
                # Finished packs are discrete units; never suggest a fraction
                # such as 0.2 of a 50 kg bag or 2.5 retail boxes.
                precision_rounding=max(line.product_uom_id.rounding, 1.0),
                rounding_method="DOWN",
            )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if not self.product_id:
            return
        self.product_uom_id = self.product_id.uom_id
        self.location_dest_id = self.production_id.location_dest_id
        if self.output_classification == "primary_packaged":
            self.net_content_qty = self.product_id.net_content_qty
            self.net_content_uom_id = self.product_id.net_content_uom_id
            self.bulk_equivalent_product_id = self.product_id.bulk_equivalent_product_id
            recipe = self.product_id.packaging_recipe_id or self.env["mrp.packaging.recipe"].effective_recipe(
                self.product_id, self.production_id.company_id,
                fields.Date.to_date(self.production_id.date_start) if self.production_id.date_start else None,
            )
            self.packaging_recipe_id = recipe
            self.packaging_recipe_version = recipe.version

    @api.constrains(
        "product_id", "output_classification", "planned_qty", "actual_qty", "product_uom_id",
        "net_content_qty", "net_content_uom_id", "bulk_equivalent_product_id",
        "packaging_recipe_id", "company_id"
    )
    def _check_output_line(self):
        for line in self:
            if line.planned_qty < 0 or line.actual_qty < 0:
                raise ValidationError("Planned and Actual Output quantities cannot be negative.")
            duplicate = self.search_count([
                ("production_id", "=", line.production_id.id),
                ("product_id", "=", line.product_id.id),
                ("id", "!=", line.id),
            ])
            if duplicate:
                raise ValidationError("The same output product cannot appear twice on one Manufacturing Order.")
            if line.product_uom_id.category_id != line.product_id.uom_id.category_id:
                raise ValidationError("Output Product and UoM are incompatible.")
            if line.product_id.company_id and line.product_id.company_id != line.company_id:
                raise ValidationError("Output Product and Manufacturing Order companies must match.")
            if line.output_classification == "primary_packaged":
                if line.net_content_qty <= 0 or not line.net_content_uom_id:
                    raise ValidationError("Primary Packaged Output requires valid Net Content.")
                if not line.bulk_equivalent_product_id:
                    raise ValidationError("Primary Packaged Output requires a Bulk Equivalent Product.")
                if not line.packaging_recipe_id:
                    raise ValidationError("Primary Packaged Output requires a Packaging Recipe.")
                if line.net_content_uom_id.category_id != line.bulk_equivalent_product_id.uom_id.category_id:
                    raise ValidationError("Net Content and Bulk Product UoMs are incompatible.")
                if line.packaging_recipe_id.product_id != line.product_id:
                    raise ValidationError("Packaging Recipe must belong to the selected output product.")
                if line.packaging_recipe_id.company_id != line.company_id:
                    raise ValidationError("Packaging Recipe and Manufacturing Order companies must match.")
            if line.output_classification == "primary_bulk" and line.product_id != line.production_id.bulk_product_id:
                raise ValidationError("Primary Bulk Output must use the Manufacturing Order bulk product.")

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        productions = lines.production_id
        for line in lines:
            if line.packaging_recipe_id:
                line.packaging_recipe_version = line.packaging_recipe_id.version
        if not self.env.context.get("skip_multi_output_sync"):
            productions._sync_primary_bulk_output_line()
            productions._refresh_prepared_draft_packaging()
        return lines

    def write(self, vals):
        result = super().write(vals)
        if "packaging_recipe_id" in vals:
            for line in self:
                line.packaging_recipe_version = line.packaging_recipe_id.version
        if not self.env.context.get("skip_multi_output_sync"):
            self.production_id._sync_primary_bulk_output_line()
            if "actual_qty" in vals:
                self.production_id._refresh_actual_packaging_calculations()
            if {
                "product_id", "output_classification", "planned_qty", "product_uom_id",
                "packaging_recipe_id",
            } & set(vals):
                self.production_id._refresh_prepared_draft_packaging()
        return result

    def unlink(self):
        productions = self.production_id
        prepared = productions.filtered(
            lambda production: production.state == "draft"
            and (
                production.recipe_snapshot_ids
                or production.packaging_line_ids
                or production.move_raw_ids.filtered(
                    lambda move: move.component_source == "packaging_recipe"
                )
            )
        )
        result = super().unlink()
        if not self.env.context.get("skip_multi_output_sync"):
            productions._sync_primary_bulk_output_line()
            prepared._refresh_prepared_draft_packaging()
        return result


class MrpProductionPackagingLine(models.Model):
    _name = "mrp.production.packaging.line"
    _description = "Manufacturing Packaging Calculation Line"
    _order = "finished_product_id, packaging_product_id, id"
    _check_company_auto = True

    production_id = fields.Many2one("mrp.production", required=True, ondelete="cascade", index=True, check_company=True)
    output_line_id = fields.Many2one("mrp.production.output.line", required=True, ondelete="cascade", index=True, check_company=True)
    recipe_snapshot_line_id = fields.Many2one(
        "mrp.production.recipe.snapshot.line", required=True, ondelete="cascade", index=True, check_company=True
    )
    finished_product_id = fields.Many2one("product.product", required=True, check_company=True)
    packaging_product_id = fields.Many2one("product.product", required=True, check_company=True)
    qty_per_unit = fields.Float(required=True, digits="Product Unit of Measure")
    planned_output_qty = fields.Float(digits="Product Unit of Measure")
    planned_packaging_qty = fields.Float(digits="Product Unit of Measure")
    actual_output_qty = fields.Float(digits="Product Unit of Measure")
    expected_actual_packaging_qty = fields.Float(digits="Product Unit of Measure")
    actual_consumed_qty = fields.Float(digits="Product Unit of Measure")
    product_uom_id = fields.Many2one("uom.uom", required=True)
    rounding_method = fields.Selection(ROUNDING_SELECTION, required=True)
    wastage_percentage = fields.Float()
    variance_qty = fields.Float(compute="_compute_variance", store=True, digits="Product Unit of Measure")
    variance_percentage = fields.Float(compute="_compute_variance", store=True)
    variance_reason = fields.Char()
    stock_move_id = fields.Many2one("stock.move", readonly=True, copy=False, check_company=True)
    operation_id = fields.Many2one("mrp.routing.workcenter", check_company=True)
    company_id = fields.Many2one(related="production_id.company_id", store=True, index=True)

    @api.depends("actual_consumed_qty", "planned_packaging_qty")
    def _compute_variance(self):
        for line in self:
            # The review's Required Quantity is the planned packaging demand,
            # so variance must use that same value.  Comparing against the
            # expected quantity for an as-yet unrecorded finished output made
            # an untouched line misleadingly display a zero variance.
            line.variance_qty = line.actual_consumed_qty - line.planned_packaging_qty
            line.variance_percentage = (
                line.variance_qty / line.planned_packaging_qty * 100.0
                if line.planned_packaging_qty else 0.0
            )

    @api.model
    def calculate_requirement(self, output_qty, qty_per_unit, wastage_percentage, rounding_method, uom):
        adjusted = output_qty * qty_per_unit * (1.0 + wastage_percentage / 100.0)
        if rounding_method == "no_rounding":
            return adjusted
        if rounding_method == "round_up":
            return float_round(adjusted, precision_rounding=uom.rounding, rounding_method="UP")
        if rounding_method == "round_nearest":
            return float_round(adjusted, precision_rounding=1.0, rounding_method="HALF-UP")
        return float_round(adjusted, precision_rounding=uom.rounding, rounding_method="HALF-UP")
