from psycopg2.errors import UniqueViolation

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero


class StockMove(models.Model):
    _inherit = "stock.move"

    downstream_manufacturing_enabled = fields.Boolean(
        related="byproduct_id.enable_downstream_manufacturing",
        string="Downstream Manufacturing Enabled",
        readonly=True,
    )
    downstream_production_ids = fields.One2many(
        "mrp.production",
        "source_byproduct_move_id",
        string="Downstream Manufacturing Orders",
    )
    downstream_production_id = fields.Many2one(
        "mrp.production",
        string="Downstream Manufacturing Order",
        compute="_compute_downstream_production_id",
    )

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

    @api.depends("downstream_production_ids")
    def _compute_downstream_production_id(self):
        for move in self:
            move.downstream_production_id = move.downstream_production_ids[:1]

    def action_create_or_open_downstream_mo(self):
        self.ensure_one()
        self.check_access_rights("read")
        self.check_access_rule("read")

        existing_production = self.downstream_production_ids[:1]
        if existing_production:
            return self._downstream_production_action(existing_production)
        if not self.byproduct_id or not self.byproduct_id.enable_downstream_manufacturing:
            raise UserError(_("Downstream manufacturing is not enabled for this by-product."))
        if not self.production_id:
            raise UserError(_("This by-product move is not linked to a source Manufacturing Order."))

        downstream_bom, downstream_product, component_qty = (
            self.byproduct_id._get_downstream_configuration()
        )
        if downstream_bom.company_id and downstream_bom.company_id != self.company_id:
            raise UserError(_("The downstream BoM must belong to the by-product move company."))
        if downstream_product.company_id and downstream_product.company_id != self.company_id:
            raise UserError(_("The downstream finished product must belong to the by-product move company."))

        source_qty = self.quantity
        if self.state != "done" and float_is_zero(
            source_qty, precision_rounding=self.product_uom.rounding
        ):
            source_qty = self.product_uom_qty
        if float_compare(source_qty, 0.0, precision_rounding=self.product_uom.rounding) <= 0:
            raise UserError(
                _("Enter a positive produced or planned quantity for %(product)s first.", product=self.product_id.display_name)
            )
        source_qty_in_product_uom = self.product_uom._compute_quantity(
            source_qty,
            self.product_id.uom_id,
            round=False,
        )
        downstream_qty = (
            source_qty_in_product_uom / component_qty * downstream_bom.product_qty
        )
        if float_compare(
            downstream_qty,
            0.0,
            precision_rounding=downstream_bom.product_uom_id.rounding,
        ) <= 0:
            raise UserError(_("The calculated downstream Manufacturing Order quantity must be positive."))

        production_values = {
            "product_id": downstream_product.id,
            "product_qty": downstream_qty,
            "product_uom_id": downstream_bom.product_uom_id.id,
            "bom_id": downstream_bom.id,
            "company_id": self.company_id.id,
            "origin": _(
                "%(source_mo)s / %(byproduct)s",
                source_mo=self.production_id.name,
                byproduct=self.product_id.display_name,
            ),
            "source_byproduct_move_id": self.id,
        }
        if downstream_bom.manufacturing_workflow == "custom_multi_output":
            production_values.update({
                "manufacturing_workflow": downstream_bom.manufacturing_workflow,
                "custom_process_type": downstream_bom.custom_process_type,
                "bulk_product_id": downstream_product.id,
                "bulk_uom_id": downstream_bom.product_uom_id.id,
                "planned_usable_output_qty": downstream_qty,
            })
        Production = self.env["mrp.production"]
        try:
            with self.env.cr.savepoint():
                downstream_production = Production.create(production_values)
        except UniqueViolation as error:
            downstream_production = Production.search(
                [("source_byproduct_move_id", "=", self.id)], limit=1
            )
            if not downstream_production:
                raise UserError(
                    _(
                        "Another request has already created the downstream Manufacturing Order. "
                        "Refresh this Manufacturing Order and use Create / Open MO again."
                    )
                ) from error
        self.invalidate_recordset(["downstream_production_ids", "downstream_production_id"])
        return self._downstream_production_action(downstream_production)

    def _downstream_production_action(self, production):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Downstream Manufacturing Order"),
            "res_model": "mrp.production",
            "view_mode": "form",
            "views": [(self.env.ref("mrp.mrp_production_form_view").id, "form")],
            "res_id": production.id,
            "target": "current",
        }

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
