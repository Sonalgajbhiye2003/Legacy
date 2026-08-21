from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    legacy_build_asset_model_id = fields.Many2one(
        "account.asset", string="Build Asset Model", check_company=True, domain="[('state', '=', 'model')]"
    )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    legacy_build_asset_model_id = fields.Many2one(related="company_id.legacy_build_asset_model_id", readonly=False)


class AccountAsset(models.Model):
    _inherit = "account.asset"

    legacy_repair_order_id = fields.Many2one("repair.order", string="Build Order", index=True, copy=False, check_company=True, ondelete="restrict")
    legacy_maintenance_request_id = fields.Many2one("maintenance.request", index=True, copy=False, check_company=True, ondelete="restrict")
    legacy_equipment_id = fields.Many2one("maintenance.equipment", index=True, copy=False, check_company=True, ondelete="restrict")

    _sql_constraints = [("legacy_repair_order_unique", "unique(legacy_repair_order_id)", "A Build Order can have only one fixed asset.")]


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    legacy_asset_id = fields.Many2one("account.asset", string="Fixed Asset", copy=False, readonly=True, check_company=True, ondelete="restrict")


class RepairOrder(models.Model):
    _inherit = "repair.order"

    legacy_asset_id = fields.Many2one("account.asset", string="Fixed Asset", copy=False, readonly=True, check_company=True, ondelete="restrict")

    def _legacy_create_or_link_asset(self, ppe_line):
        self.ensure_one()
        asset = self.legacy_asset_id or ppe_line.asset_ids[:1] or self.env["account.asset"].search([("legacy_repair_order_id", "=", self.id)], limit=1)
        if not asset:
            values = {
                "name": self.legacy_machine_name,
                "company_id": self.company_id.id,
                "original_move_line_ids": [(6, 0, ppe_line.ids)],
                "acquisition_date": self.legacy_commissioning_date,
                "legacy_repair_order_id": self.id,
                "legacy_maintenance_request_id": self.legacy_maintenance_request_id.id,
                "legacy_equipment_id": self.legacy_equipment_id.id,
            }
            model = self.company_id.legacy_build_asset_model_id
            if model:
                values["model_id"] = model.id
            asset = self.env["account.asset"].create(values)
            if model:
                asset._onchange_model_id()
                asset.validate()
        else:
            asset.write({"legacy_repair_order_id": self.id, "legacy_maintenance_request_id": self.legacy_maintenance_request_id.id, "legacy_equipment_id": self.legacy_equipment_id.id})
        self.legacy_asset_id = asset
        self.legacy_equipment_id.legacy_asset_id = asset
        return asset
