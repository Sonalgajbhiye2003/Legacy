from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    legacy_cwip_account_id = fields.Many2one(
        "account.account",
        string="Capital Work-in-Progress Account",
        check_company=True,
        domain="[('deprecated', '=', False), ('company_id', '=', id)]",
    )
    legacy_repair_expense_account_id = fields.Many2one(
        "account.account",
        string="Default Repair and Maintenance Expense Account",
        check_company=True,
        domain="[('deprecated', '=', False), ('company_id', '=', id)]",
    )
    legacy_ppe_account_id = fields.Many2one(
        "account.account",
        string="Property, Plant and Equipment Account",
        check_company=True,
        domain="[('deprecated', '=', False), ('company_id', '=', id)]",
    )
    legacy_accumulated_depreciation_account_id = fields.Many2one(
        "account.account",
        string="Accumulated Depreciation Account",
        check_company=True,
        domain="[('deprecated', '=', False), ('company_id', '=', id)]",
    )
    legacy_inventory_account_id = fields.Many2one(
        "account.account",
        string="Spare/Raw Material Inventory Account",
        check_company=True,
        domain="[('deprecated', '=', False), ('company_id', '=', id)]",
    )
    legacy_labour_clearing_account_id = fields.Many2one(
        "account.account",
        string="Labour Clearing/Recovery Account",
        check_company=True,
        domain="[('deprecated', '=', False), ('company_id', '=', id)]",
    )
    legacy_labour_journal_id = fields.Many2one(
        "account.journal",
        string="Maintenance Labour Journal",
        check_company=True,
        domain="[('type', '=', 'general'), ('company_id', '=', id)]",
    )
    legacy_material_journal_id = fields.Many2one(
        "account.journal",
        string="Manual Material Consumption Journal",
        check_company=True,
        domain="[('type', '=', 'general'), ('company_id', '=', id)]",
    )
    legacy_capitalization_journal_id = fields.Many2one(
        "account.journal",
        string="Capitalization Journal",
        check_company=True,
        domain="[('type', '=', 'general'), ('company_id', '=', id)]",
    )
    legacy_capex_location_id = fields.Many2one(
        "stock.location",
        string="CAPEX Consumption Location",
        check_company=True,
        domain="[('usage', '=', 'production'), ('company_id', '=', id)]",
    )
    legacy_opex_location_id = fields.Many2one(
        "stock.location",
        string="OPEX Consumption Location",
        check_company=True,
        domain="[('usage', '=', 'production'), ('company_id', '=', id)]",
    )
    legacy_labour_posting_mode = fields.Selection(
        [
            ("reporting", "Reporting Only"),
            ("post_approved", "Post Approved Labour"),
        ],
        string="Maintenance Labour Posting Mode",
        required=True,
        default="reporting",
    )
    legacy_zero_cost_policy = fields.Selection(
        [
            ("block", "Block"),
            ("finance_exception", "Allow with Finance Approval"),
        ],
        string="Zero-Cost Material Issue Policy",
        required=True,
        default="block",
    )
    legacy_default_labour_hourly_rate = fields.Monetary(
        string="Default Maintenance Labour Hourly Rate",
        currency_field="currency_id",
        default=0.0,
    )

    @api.constrains(
        "legacy_cwip_account_id",
        "legacy_repair_expense_account_id",
        "legacy_ppe_account_id",
        "legacy_accumulated_depreciation_account_id",
        "legacy_inventory_account_id",
        "legacy_labour_clearing_account_id",
        "legacy_labour_journal_id",
        "legacy_material_journal_id",
        "legacy_capitalization_journal_id",
        "legacy_capex_location_id",
        "legacy_opex_location_id",
    )
    def _check_legacy_configuration_company(self):
        account_fields = (
            "legacy_cwip_account_id",
            "legacy_repair_expense_account_id",
            "legacy_ppe_account_id",
            "legacy_accumulated_depreciation_account_id",
            "legacy_inventory_account_id",
            "legacy_labour_clearing_account_id",
        )
        journal_fields = (
            "legacy_labour_journal_id",
            "legacy_material_journal_id",
            "legacy_capitalization_journal_id",
        )
        location_fields = ("legacy_capex_location_id", "legacy_opex_location_id")
        for company in self:
            for field_name in account_fields + journal_fields + location_fields:
                record = company[field_name]
                if record and record.company_id != company:
                    raise ValidationError(
                        _("%(record)s must belong to %(company)s.", record=record.display_name, company=company.display_name)
                    )
            for field_name in journal_fields:
                journal = company[field_name]
                if journal and journal.type != "general":
                    raise ValidationError(_("%(journal)s must be a Miscellaneous journal.", journal=journal.display_name))
            for field_name in location_fields:
                location = company[field_name]
                if location and location.usage != "production":
                    raise ValidationError(_("%(location)s must be a Production location.", location=location.display_name))
            if company.legacy_capex_location_id and company.legacy_capex_location_id == company.legacy_opex_location_id:
                raise ValidationError(_("CAPEX and OPEX consumption locations must be different."))

    def _legacy_validate_account(self, account, label):
        self.ensure_one()
        if not account:
            raise ValidationError(_("Configure %(label)s for %(company)s first.", label=label, company=self.display_name))
        if account.company_id != self or account.deprecated:
            raise ValidationError(_("%(label)s is not valid for %(company)s.", label=label, company=self.display_name))
        return account

    def _legacy_validate_journal(self, journal, label):
        self.ensure_one()
        if not journal:
            raise ValidationError(_("Configure %(label)s for %(company)s first.", label=label, company=self.display_name))
        if journal.company_id != self or journal.type != "general":
            raise ValidationError(_("%(label)s is not valid for %(company)s.", label=label, company=self.display_name))
        return journal

    def _legacy_validate_location(self, location, label):
        self.ensure_one()
        if not location:
            raise ValidationError(_("Configure %(label)s for %(company)s first.", label=label, company=self.display_name))
        if location.company_id != self or location.usage != "production":
            raise ValidationError(_("%(label)s is not valid for %(company)s.", label=label, company=self.display_name))
        return location

    def _legacy_check_material_configuration(self, expense_type, automated=False):
        self.ensure_one()
        if expense_type == "capex":
            debit_account = self._legacy_validate_account(self.legacy_cwip_account_id, _("CWIP Account"))
            location = self._legacy_validate_location(self.legacy_capex_location_id, _("CAPEX Consumption Location"))
        elif expense_type == "opex":
            debit_account = self._legacy_validate_account(self.legacy_repair_expense_account_id, _("Repair Expense Account"))
            location = self._legacy_validate_location(self.legacy_opex_location_id, _("OPEX Consumption Location"))
        else:
            raise ValidationError(_("CAPEX/OPEX classification is required."))
        result = {"debit_account": debit_account, "location": location}
        if not automated:
            result.update(
                inventory_account=self._legacy_validate_account(self.legacy_inventory_account_id, _("Inventory Account")),
                journal=self._legacy_validate_journal(self.legacy_material_journal_id, _("Material Consumption Journal")),
            )
        return result

