from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    legacy_cwip_account_id = fields.Many2one(related="company_id.legacy_cwip_account_id", readonly=False)
    legacy_repair_expense_account_id = fields.Many2one(related="company_id.legacy_repair_expense_account_id", readonly=False)
    legacy_ppe_account_id = fields.Many2one(related="company_id.legacy_ppe_account_id", readonly=False)
    legacy_accumulated_depreciation_account_id = fields.Many2one(related="company_id.legacy_accumulated_depreciation_account_id", readonly=False)
    legacy_inventory_account_id = fields.Many2one(related="company_id.legacy_inventory_account_id", readonly=False)
    legacy_labour_clearing_account_id = fields.Many2one(related="company_id.legacy_labour_clearing_account_id", readonly=False)
    legacy_labour_journal_id = fields.Many2one(related="company_id.legacy_labour_journal_id", readonly=False)
    legacy_material_journal_id = fields.Many2one(related="company_id.legacy_material_journal_id", readonly=False)
    legacy_capitalization_journal_id = fields.Many2one(related="company_id.legacy_capitalization_journal_id", readonly=False)
    legacy_capex_location_id = fields.Many2one(related="company_id.legacy_capex_location_id", readonly=False)
    legacy_opex_location_id = fields.Many2one(related="company_id.legacy_opex_location_id", readonly=False)
    legacy_labour_posting_mode = fields.Selection(related="company_id.legacy_labour_posting_mode", readonly=False)
    legacy_zero_cost_policy = fields.Selection(related="company_id.legacy_zero_cost_policy", readonly=False)
    legacy_default_labour_hourly_rate = fields.Monetary(related="company_id.legacy_default_labour_hourly_rate", readonly=False)

