from datetime import date

from odoo import api, fields, models
from odoo.exceptions import ValidationError


ROUNDING_SELECTION = [
    ("no_rounding", "No Rounding"),
    ("round_up", "Round Up"),
    ("round_nearest", "Round to Nearest Unit"),
    ("product_uom_rounding", "Product UoM Rounding"),
]


class MrpPackagingRecipe(models.Model):
    _name = "mrp.packaging.recipe"
    _description = "Packaging Recipe"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "product_id, valid_from desc, version desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(default=lambda self: self.env["ir.sequence"].next_by_code("mrp.packaging.recipe"), tracking=True)
    product_id = fields.Many2one(
        "product.product", required=True, index=True, check_company=True, tracking=True,
        domain="[('packaging_enabled', '=', True)]"
    )
    base_qty = fields.Float(required=True, default=1.0, digits="Product Unit of Measure", tracking=True)
    base_uom_id = fields.Many2one("uom.uom", required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True, tracking=True
    )
    operation_id = fields.Many2one("mrp.routing.workcenter", check_company=True, tracking=True)
    workcenter_id = fields.Many2one("mrp.workcenter", check_company=True, tracking=True)
    valid_from = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    valid_to = fields.Date(tracking=True)
    version = fields.Char(required=True, default="1.0", tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    notes = fields.Html()
    line_ids = fields.One2many("mrp.packaging.recipe.line", "recipe_id", copy=True)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.base_uom_id = self.product_id.uom_id

    @api.constrains("base_qty", "base_uom_id", "product_id", "valid_from", "valid_to", "active", "company_id")
    def _check_recipe(self):
        for recipe in self:
            if recipe.base_qty <= 0:
                raise ValidationError("Recipe Base Quantity must be greater than zero.")
            if recipe.product_id and recipe.base_uom_id.category_id != recipe.product_id.uom_id.category_id:
                raise ValidationError("Recipe Base UoM must match the finished product UoM category.")
            if recipe.product_id.company_id and recipe.product_id.company_id != recipe.company_id:
                raise ValidationError("Recipe and product companies must match.")
            if recipe.valid_to and recipe.valid_to < recipe.valid_from:
                raise ValidationError("Recipe Valid To cannot be earlier than Valid From.")
            if not recipe.active or not recipe.product_id:
                continue
            end_date = recipe.valid_to or date.max
            overlap = self.search_count([
                ("id", "!=", recipe.id),
                ("active", "=", True),
                ("product_id", "=", recipe.product_id.id),
                ("company_id", "=", recipe.company_id.id),
                ("valid_from", "<=", end_date),
                "|", ("valid_to", "=", False), ("valid_to", ">=", recipe.valid_from),
            ])
            if overlap:
                raise ValidationError("Active recipe dates cannot overlap for the same product and company.")

    @api.model
    def effective_recipe(self, product, company, effective_date=None):
        effective_date = effective_date or fields.Date.context_today(self)
        return self.search([
            ("product_id", "=", product.id),
            ("company_id", "=", company.id),
            ("active", "=", True),
            ("valid_from", "<=", effective_date),
            "|", ("valid_to", "=", False), ("valid_to", ">=", effective_date),
        ], order="valid_from desc, id desc", limit=1)


class MrpPackagingRecipeLine(models.Model):
    _name = "mrp.packaging.recipe.line"
    _description = "Packaging Recipe Line"
    _order = "sequence, id"
    _check_company_auto = True

    recipe_id = fields.Many2one("mrp.packaging.recipe", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="recipe_id.company_id", store=True, index=True)
    packaging_product_id = fields.Many2one(
        "product.product", required=True, check_company=True, domain="[('type', 'in', ['product', 'consu'])]"
    )
    qty_per_base = fields.Float(required=True, digits="Product Unit of Measure")
    product_uom_id = fields.Many2one("uom.uom", required=True)
    rounding_method = fields.Selection(ROUNDING_SELECTION, required=True, default="product_uom_rounding")
    wastage_percentage = fields.Float(default=0.0)
    operation_id = fields.Many2one("mrp.routing.workcenter", check_company=True)
    allow_manual_adjustment = fields.Boolean(default=False)
    sequence = fields.Integer(default=10)

    @api.onchange("packaging_product_id")
    def _onchange_packaging_product_id(self):
        if self.packaging_product_id:
            self.product_uom_id = self.packaging_product_id.uom_id

    @api.constrains("packaging_product_id", "qty_per_base", "product_uom_id", "wastage_percentage")
    def _check_line(self):
        for line in self:
            if line.qty_per_base <= 0:
                raise ValidationError("Packaging Quantity per Base must be greater than zero.")
            if line.wastage_percentage < 0:
                raise ValidationError("Packaging wastage percentage cannot be negative.")
            if line.packaging_product_id == line.recipe_id.product_id:
                raise ValidationError("Packaging material cannot equal the finished product.")
            if line.product_uom_id.category_id != line.packaging_product_id.uom_id.category_id:
                raise ValidationError("Packaging material UoM must match its product UoM category.")
            if line.packaging_product_id.company_id and line.packaging_product_id.company_id != line.company_id:
                raise ValidationError("Packaging material and recipe companies must match.")


class MrpProductionRecipeSnapshot(models.Model):
    _name = "mrp.production.recipe.snapshot"
    _description = "Manufacturing Packaging Recipe Snapshot"
    _order = "production_id, output_line_id"
    _check_company_auto = True

    production_id = fields.Many2one("mrp.production", required=True, ondelete="cascade", index=True, check_company=True)
    output_line_id = fields.Many2one("mrp.production.output.line", required=True, ondelete="cascade", index=True, check_company=True)
    company_id = fields.Many2one(related="production_id.company_id", store=True, index=True)
    recipe_id = fields.Many2one("mrp.packaging.recipe", required=True, ondelete="restrict", check_company=True)
    recipe_version = fields.Char(required=True)
    finished_product_id = fields.Many2one("product.product", required=True, check_company=True)
    base_qty = fields.Float(required=True, digits="Product Unit of Measure")
    base_uom_id = fields.Many2one("uom.uom", required=True)
    line_ids = fields.One2many("mrp.production.recipe.snapshot.line", "snapshot_id", copy=False)


class MrpProductionRecipeSnapshotLine(models.Model):
    _name = "mrp.production.recipe.snapshot.line"
    _description = "Manufacturing Packaging Recipe Snapshot Line"
    _order = "sequence, id"
    _check_company_auto = True

    snapshot_id = fields.Many2one("mrp.production.recipe.snapshot", required=True, ondelete="cascade", index=True)
    production_id = fields.Many2one(related="snapshot_id.production_id", store=True, index=True)
    company_id = fields.Many2one(related="snapshot_id.company_id", store=True, index=True)
    packaging_product_id = fields.Many2one("product.product", required=True, check_company=True)
    qty_per_unit = fields.Float(required=True, digits="Product Unit of Measure")
    product_uom_id = fields.Many2one("uom.uom", required=True)
    rounding_method = fields.Selection(ROUNDING_SELECTION, required=True)
    wastage_percentage = fields.Float()
    operation_id = fields.Many2one("mrp.routing.workcenter", check_company=True)
    workcenter_id = fields.Many2one("mrp.workcenter", check_company=True)
    allow_manual_adjustment = fields.Boolean()
    sequence = fields.Integer(default=10)
