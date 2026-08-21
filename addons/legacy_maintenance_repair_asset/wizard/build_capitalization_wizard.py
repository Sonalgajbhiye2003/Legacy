from odoo import fields, models


class LegacyBuildCapitalizationWizard(models.TransientModel):
    _inherit = "legacy.build.capitalization.wizard"

    asset_model_id = fields.Many2one(related="company_id.legacy_build_asset_model_id", readonly=True)
