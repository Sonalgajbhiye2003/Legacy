from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    component_source = fields.Selection(
        [
            ("process_bom", "Process BoM"),
            ("packaging_recipe", "Packaging Recipe"),
            ("manual", "Manual"),
        ],
        default="manual",
        index=True,
        copy=True,
    )
    expected_packaging_qty = fields.Float(digits="Product Unit of Measure", copy=True)
    actual_packaging_qty = fields.Float(
        compute="_compute_packaging_variance", store=True, digits="Product Unit of Measure"
    )
    packaging_variance_qty = fields.Float(
        compute="_compute_packaging_variance", store=True, digits="Product Unit of Measure"
    )
    packaging_line_ids = fields.One2many(
        "mrp.production.packaging.line", "stock_move_id", copy=False
    )
    expected_byproduct_qty = fields.Float(
        string="Expected Quantity", compute="_compute_byproduct_variance", store=True,
        digits="Product Unit of Measure",
    )
    actual_byproduct_qty = fields.Float(
        string="Actual Quantity", compute="_compute_byproduct_variance", store=True,
        digits="Product Unit of Measure",
    )
    byproduct_variance_qty = fields.Float(
        string="Variance", compute="_compute_byproduct_variance", store=True,
        digits="Product Unit of Measure",
    )
    byproduct_variance_percentage = fields.Float(
        string="Variance Percentage", compute="_compute_byproduct_variance", store=True,
    )
    byproduct_variance_reason = fields.Char(string="Variance Reason")

    @api.depends("quantity", "expected_packaging_qty", "component_source")
    def _compute_packaging_variance(self):
        for move in self:
            if move.component_source == "packaging_recipe":
                move.actual_packaging_qty = move.quantity
                move.packaging_variance_qty = move.quantity - move.expected_packaging_qty
            else:
                move.actual_packaging_qty = 0.0
                move.packaging_variance_qty = 0.0

    @api.depends("byproduct_id", "product_uom_qty", "quantity")
    def _compute_byproduct_variance(self):
        for move in self:
            if move.byproduct_id:
                move.expected_byproduct_qty = move.product_uom_qty
                move.actual_byproduct_qty = move.quantity
                move.byproduct_variance_qty = move.quantity - move.product_uom_qty
                move.byproduct_variance_percentage = (
                    move.byproduct_variance_qty / move.product_uom_qty * 100.0
                    if move.product_uom_qty else 0.0
                )
            else:
                move.expected_byproduct_qty = 0.0
                move.actual_byproduct_qty = 0.0
                move.byproduct_variance_qty = 0.0
                move.byproduct_variance_percentage = 0.0
