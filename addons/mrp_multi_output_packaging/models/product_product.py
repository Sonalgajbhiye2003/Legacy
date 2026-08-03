from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductProduct(models.Model):
    _inherit = "product.product"

    packaging_enabled = fields.Boolean(string="Packaging Enabled")
    net_content_qty = fields.Float(string="Net Content", digits="Product Unit of Measure")
    net_content_uom_id = fields.Many2one("uom.uom", string="Net Content UoM")
    bulk_equivalent_product_id = fields.Many2one(
        "product.product", string="Bulk Equivalent Product", check_company=True
    )
    packaging_recipe_id = fields.Many2one(
        "mrp.packaging.recipe",
        string="Default Packaging Recipe",
        check_company=True,
        domain="[('product_id', '=', id), ('active', '=', True)]",
    )
    default_packaging_operation_id = fields.Many2one(
        "mrp.routing.workcenter", string="Default Packaging Operation", check_company=True
    )
    default_packaging_workcenter_id = fields.Many2one(
        "mrp.workcenter", string="Default Packaging Work Centre", check_company=True
    )
    packaging_recipe_count = fields.Integer(compute="_compute_packaging_recipe_count")

    def _compute_packaging_recipe_count(self):
        grouped = self.env["mrp.packaging.recipe"]._read_group(
            [("product_id", "in", self.ids)], ["product_id"], ["__count"]
        )
        counts = {product.id: count for product, count in grouped}
        for product in self:
            product.packaging_recipe_count = counts.get(product.id, 0)

    @api.constrains(
        "packaging_enabled", "net_content_qty", "net_content_uom_id",
        "bulk_equivalent_product_id", "packaging_recipe_id"
    )
    def _check_packaging_configuration(self):
        for product in self:
            if not product.packaging_enabled:
                continue
            if product.net_content_qty <= 0:
                raise ValidationError("Net Content must be greater than zero.")
            if not product.net_content_uom_id:
                raise ValidationError("Net Content UoM is required for a packaged product.")
            if not product.bulk_equivalent_product_id:
                raise ValidationError("Bulk Equivalent Product is required for a packaged product.")
            if product.bulk_equivalent_product_id == product:
                raise ValidationError("A packaged product cannot be its own Bulk Equivalent Product.")
            if product.net_content_uom_id.category_id != product.bulk_equivalent_product_id.uom_id.category_id:
                raise ValidationError("Net Content UoM must have the same category as the bulk product UoM.")
            if product.packaging_recipe_id and product.packaging_recipe_id.product_id != product:
                raise ValidationError("The default packaging recipe must belong to this product variant.")
            recipe_company = product.packaging_recipe_id.company_id
            if recipe_company and product.company_id and recipe_company != product.company_id:
                raise ValidationError("Product and packaging recipe companies must match.")

    def action_view_packaging_recipes(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "mrp_multi_output_packaging.action_mrp_packaging_recipe"
        )
        action["domain"] = [("product_id", "=", self.id)]
        action["context"] = {"default_product_id": self.id, "default_company_id": self.company_id.id}
        return action
