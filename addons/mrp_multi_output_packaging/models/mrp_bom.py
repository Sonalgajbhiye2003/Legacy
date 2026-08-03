from odoo import api, fields, models
from odoo.exceptions import ValidationError


WORKFLOW_SELECTION = [
    ("standard", "Standard Odoo"),
    ("custom_multi_output", "Custom Multi-Output"),
]

PROCESS_SELECTION = [
    ("integrated_production_packaging", "Integrated Production and Packaging"),
    ("multi_variant_packaging", "Multi-Variant Packaging"),
]


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    manufacturing_workflow = fields.Selection(
        WORKFLOW_SELECTION,
        string="Manufacturing Workflow",
        required=True,
        default="standard",
        tracking=True,
    )
    custom_process_type = fields.Selection(PROCESS_SELECTION, string="Custom Process Type", tracking=True)
    default_packaged_product_id = fields.Many2one(
        "product.product",
        string="Packaged Product",
        check_company=True,
        domain="[('packaging_enabled', '=', True), ('bulk_equivalent_product_id', '=', product_id)]",
        help="Packaged product added automatically to Manufacturing Orders using this BoM.",
    )

    @api.onchange("manufacturing_workflow")
    def _onchange_manufacturing_workflow(self):
        if self.manufacturing_workflow == "standard":
            self.custom_process_type = False

    @api.constrains("manufacturing_workflow", "custom_process_type", "default_packaged_product_id", "product_id")
    def _check_custom_process_type(self):
        for bom in self:
            if bom.manufacturing_workflow == "custom_multi_output" and not bom.custom_process_type:
                raise ValidationError("Custom Process Type is required for a Custom Multi-Output BoM.")
            if bom.manufacturing_workflow == "standard" and bom.custom_process_type:
                raise ValidationError("Custom Process Type must be empty for a Standard Odoo BoM.")
            if (
                bom.default_packaged_product_id
                and bom.default_packaged_product_id.bulk_equivalent_product_id != bom.product_id
            ):
                raise ValidationError("The packaged product must use the BoM product as its Bulk Equivalent Product.")
