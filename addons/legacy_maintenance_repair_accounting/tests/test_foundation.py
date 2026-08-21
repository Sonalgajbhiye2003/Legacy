from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged("post_install", "-at_install", "legacy_maintenance_foundation")
class TestMaintenanceRepairFoundation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create({"name": "Legacy Foundation A", "sequence_prefix": "LFA"})
        cls.other_company = cls.env["res.company"].create({"name": "Legacy Foundation B", "sequence_prefix": "LFB"})
        cls.account = cls.env["account.account"].create(
            {"name": "Foundation CWIP", "code": "TSTCWIP", "account_type": "asset_current", "company_id": cls.company.id}
        )
        cls.other_account = cls.env["account.account"].create(
            {"name": "Other CWIP", "code": "TSTOCW", "account_type": "asset_current", "company_id": cls.other_company.id}
        )
        cls.journal = cls.env["account.journal"].create(
            {"name": "Foundation Material", "code": "TFMJ", "type": "general", "company_id": cls.company.id}
        )
        cls.capex_location = cls.env["stock.location"].create(
            {"name": "Foundation CAPEX", "usage": "production", "company_id": cls.company.id}
        )
        cls.opex_location = cls.env["stock.location"].create(
            {"name": "Foundation OPEX", "usage": "production", "company_id": cls.company.id}
        )

    def test_01_module_and_groups_installed(self):
        module = self.env["ir.module.module"].search([("name", "=", "legacy_maintenance_repair_accounting")])
        self.assertEqual(module.state, "installed")
        self.assertTrue(self.env.ref("legacy_maintenance_repair_accounting.group_repair_supervisor"))
        self.assertTrue(self.env.ref("legacy_maintenance_repair_accounting.view_res_config_settings_legacy_maintenance"))

    def test_02_settings_persist_per_company(self):
        settings = self.env["res.config.settings"].with_company(self.company).create(
            {
                "company_id": self.company.id,
                "legacy_cwip_account_id": self.account.id,
                "legacy_material_journal_id": self.journal.id,
                "legacy_capex_location_id": self.capex_location.id,
                "legacy_opex_location_id": self.opex_location.id,
                "legacy_default_labour_hourly_rate": 125.0,
            }
        )
        settings.execute()
        self.assertEqual(self.company.legacy_cwip_account_id, self.account)
        self.assertEqual(self.company.legacy_default_labour_hourly_rate, 125.0)
        self.assertFalse(self.other_company.legacy_cwip_account_id)

    def test_03_cross_company_configuration_is_blocked(self):
        with self.assertRaises(UserError):
            self.company.write({"legacy_cwip_account_id": self.other_account.id})

    def test_04_missing_configuration_is_explicit(self):
        with self.assertRaisesRegex(ValidationError, "CWIP"):
            self.company._legacy_check_material_configuration("capex")

    def test_05_valid_material_configuration(self):
        self.company.write(
            {
                "legacy_cwip_account_id": self.account.id,
                "legacy_inventory_account_id": self.account.id,
                "legacy_material_journal_id": self.journal.id,
                "legacy_capex_location_id": self.capex_location.id,
                "legacy_opex_location_id": self.opex_location.id,
            }
        )
        values = self.company._legacy_check_material_configuration("capex")
        self.assertEqual(values["debit_account"], self.account)
        self.assertEqual(values["location"], self.capex_location)
