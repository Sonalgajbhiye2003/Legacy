from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class LegacyBuildCapitalizationWizard(models.TransientModel):
    _name = "legacy.build.capitalization.wizard"
    _description = "Capitalize Build"

    repair_order_id = fields.Many2one("repair.order", required=True, readonly=True, check_company=True)
    company_id = fields.Many2one(related="repair_order_id.company_id", readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    material_capex = fields.Monetary(compute="_compute_amounts", currency_field="currency_id")
    labour_capex = fields.Monetary(compute="_compute_amounts", currency_field="currency_id")
    total_capitalizable_cost = fields.Monetary(compute="_compute_amounts", currency_field="currency_id")
    cwip_account_id = fields.Many2one(related="company_id.legacy_cwip_account_id", readonly=True)
    ppe_account_id = fields.Many2one(related="company_id.legacy_ppe_account_id", readonly=True)
    journal_id = fields.Many2one(related="company_id.legacy_capitalization_journal_id", readonly=True)
    accounting_date = fields.Date(required=True, default=fields.Date.context_today)
    equipment_id = fields.Many2one(related="repair_order_id.legacy_equipment_id", readonly=True)
    target_workcenter_id = fields.Many2one(related="repair_order_id.legacy_target_workcenter_id", readonly=True)
    commissioning_date = fields.Date(required=True, default=fields.Date.context_today)
    asset_availability = fields.Char(compute="_compute_asset_availability")

    @api.depends("repair_order_id.legacy_total_capex", "repair_order_id.legacy_material_cost", "repair_order_id.legacy_labour_cost")
    def _compute_amounts(self):
        for wizard in self:
            material, labour = wizard.repair_order_id._legacy_capex_lines() if wizard.repair_order_id else (self.env["stock.request"], self.env["legacy.repair.labour"])
            wizard.material_capex = sum(material.mapped("legacy_posted_value"))
            wizard.labour_capex = sum(labour.mapped("labour_cost"))
            wizard.total_capitalizable_cost = wizard.material_capex + wizard.labour_capex

    def _compute_asset_availability(self):
        installed = self.env["ir.module.module"].sudo().search_count([("name", "=", "account_asset"), ("state", "=", "installed")])
        for wizard in self:
            wizard.asset_availability = _("Available through the installed Assets bridge") if installed and "account.asset" in self.env else _("Assets is unavailable; Equipment and the capitalization entry will still be created.")

    def action_capitalize(self):
        self.ensure_one()
        if not self.env.user.has_group("legacy_maintenance_repair_accounting.group_finance_maintenance_approver"):
            raise AccessError(_("Only Finance can capitalize a Build Order."))
        order = self.repair_order_id
        self.env.cr.execute("SELECT id FROM repair_order WHERE id = %s FOR UPDATE", [order.id])
        order.invalidate_recordset()
        if order.legacy_capitalization_move_id:
            return order.action_open_legacy_capitalization()
        amount = order._legacy_check_build_readiness(self.commissioning_date)
        company = order.company_id
        journal = company._legacy_validate_journal(company.legacy_capitalization_journal_id, _("Capitalization Journal"))
        ppe = company._legacy_validate_account(company.legacy_ppe_account_id, _("PPE Account"))
        cwip = company._legacy_validate_account(company.legacy_cwip_account_id, _("CWIP Account"))
        common = {"legacy_equipment_id": order.legacy_equipment_id.id, "legacy_workcenter_id": order.legacy_target_workcenter_id.id}
        move = self.env["account.move"].create({
            "move_type": "entry", "date": self.accounting_date, "journal_id": journal.id,
            "ref": _("Build capitalization %(order)s", order=order.display_name),
            "legacy_posting_type": "capitalization", "legacy_capitalization_repair_id": order.id,
            "legacy_repair_order_id": order.id, "legacy_maintenance_request_id": order.legacy_maintenance_request_id.id,
            "legacy_equipment_id": order.legacy_equipment_id.id,
            "line_ids": [(0, 0, dict(common, name=order.legacy_machine_name, account_id=ppe.id, debit=amount, credit=0.0)), (0, 0, dict(common, name=order.legacy_machine_name, account_id=cwip.id, debit=0.0, credit=amount))],
        })
        move.action_post()
        equipment = order.legacy_equipment_id
        if not equipment:
            equipment = self.env["maintenance.equipment"].create({
                "name": order.legacy_machine_name, "company_id": company.id, "workcenter_id": order.legacy_target_workcenter_id.id,
                "legacy_commissioning_state": "under_construction", "legacy_build_order_id": order.id,
            })
        equipment.write({"workcenter_id": order.legacy_target_workcenter_id.id, "legacy_commissioning_state": "in_service", "legacy_commissioning_date": self.commissioning_date, "legacy_capitalized_cost": amount, "legacy_build_order_id": order.id})
        order.write({"legacy_equipment_id": equipment.id, "legacy_commissioning_date": self.commissioning_date, "legacy_capitalization_move_id": move.id, "legacy_capitalization_status": "capitalized"})
        ppe_line = move.line_ids.filtered(lambda line: line.account_id == ppe and line.debit > 0)[:1]
        order._legacy_create_or_link_asset(ppe_line)
        return order.action_open_legacy_capitalization()
