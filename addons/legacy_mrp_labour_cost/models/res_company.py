from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    manufacturing_labour_journal_id = fields.Many2one(
        "account.journal",
        string="Manufacturing Labour Journal",
        domain="[('type', '=', 'general'), ('company_id', '=', id)]",
        check_company=True,
        help="Miscellaneous journal used for supplementary manufacturing labour entries.",
    )
    manufacturing_labour_debit_account_id = fields.Many2one(
        "account.account",
        string="Manufacturing Labour Debit Account",
        domain="[('deprecated', '=', False), ('company_id', '=', id)]",
        check_company=True,
        help="Expense or WIP account debited when manufacturing labour is posted.",
    )
    manufacturing_labour_credit_account_id = fields.Many2one(
        "account.account",
        string="Manufacturing Labour Credit Account",
        domain="[('deprecated', '=', False), ('company_id', '=', id)]",
        check_company=True,
        help="Clearing or payable account credited when manufacturing labour is posted.",
    )
