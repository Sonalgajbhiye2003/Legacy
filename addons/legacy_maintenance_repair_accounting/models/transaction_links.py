from odoo import fields, models


class StockRequestOrder(models.Model):
    _inherit = "stock.request.order"

    legacy_maintenance_request_id = fields.Many2one(
        "maintenance.request",
        string="Maintenance Request",
        index=True,
        ondelete="restrict",
        check_company=True,
    )
    legacy_repair_order_id = fields.Many2one(
        "repair.order",
        string="Repair/Build Order",
        index=True,
        ondelete="restrict",
        check_company=True,
    )
    legacy_equipment_id = fields.Many2one(
        "maintenance.equipment",
        string="Equipment",
        index=True,
        check_company=True,
    )


class AccountMove(models.Model):
    _inherit = "account.move"

    legacy_maintenance_request_id = fields.Many2one(
        "maintenance.request",
        string="Maintenance Request",
        index=True,
        copy=False,
        ondelete="restrict",
        check_company=True,
    )
    legacy_repair_order_id = fields.Many2one(
        "repair.order",
        string="Repair/Build Order",
        index=True,
        copy=False,
        ondelete="restrict",
        check_company=True,
    )
    legacy_equipment_id = fields.Many2one(
        "maintenance.equipment",
        string="Equipment",
        index=True,
        copy=False,
        check_company=True,
    )
