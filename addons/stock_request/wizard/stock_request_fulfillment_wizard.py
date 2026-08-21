from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class StockRequestPurchaseWizard(models.TransientModel):
    _name = "stock.request.purchase.wizard"
    _description = "Create Purchase Order from Material Requisition"

    request_order_id = fields.Many2one(
        "stock.request.order",
        string="Material Requisition",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Vendor",
        required=True,
        domain="[('supplier_rank', '>', 0)]",
    )
    date_order = fields.Datetime(
        string="Order Deadline", required=True, default=fields.Datetime.now
    )

    def action_create_purchase_order(self):
        self.ensure_one()
        if not self.env.user.has_group("purchase.group_purchase_user"):
            raise AccessError(_("Only a Purchase user can create a Purchase Order."))
        request = self.request_order_id
        request._check_fulfillment_creation()
        purchase_enabled = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("stock_request.enable_purchase", "True")
            .lower()
            in ("true", "1")
        )
        if not purchase_enabled:
            raise UserError(
                _("Enable Stock Requests for Purchases in Settings first.")
            )

        order_lines = []
        for line in request.stock_request_ids:
            line_values = {
                "product_id": line.product_id.id,
                "name": line.request_reason or line.product_id.display_name,
                "product_qty": line.product_uom_qty,
                "product_uom": line.product_uom_id.id,
                "price_unit": line.estimated_unit_cost,
                "date_planned": request.expected_date or fields.Datetime.now(),
            }
            if line.analytic_account_id:
                line_values["analytic_distribution"] = {
                    str(line.analytic_account_id.id): 100.0
                }
            order_lines.append((0, 0, line_values))

        currency = (
            self.partner_id.property_purchase_currency_id
            or request.company_id.currency_id
        )
        purchase_order = self.env["purchase.order"].create(
            {
                "partner_id": self.partner_id.id,
                "company_id": request.company_id.id,
                "currency_id": currency.id,
                "date_order": self.date_order,
                "origin": request.name,
                "order_line": order_lines,
            }
        )
        request.write(
            {
                "purchase_order_ids": [(4, purchase_order.id)],
                "state": "done",
            }
        )
        request.message_post(
            body=_(
                "Purchase Order %(purchase_order)s created from this Material Requisition.",
                purchase_order=purchase_order.display_name,
            ),
            subtype_xmlid="mail.mt_note",
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Purchase Order"),
            "res_model": "purchase.order",
            "view_mode": "form",
            "res_id": purchase_order.id,
        }


class StockRequestTransferWizard(models.TransientModel):
    _name = "stock.request.transfer.wizard"
    _description = "Create Internal Transfer from Material Requisition"

    request_order_id = fields.Many2one(
        "stock.request.order",
        string="Material Requisition",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    picking_type_id = fields.Many2one(
        "stock.picking.type",
        string="Operation Type",
        required=True,
        domain="[('code', '=', 'internal'), ('company_id', '=', company_id)]",
    )
    location_id = fields.Many2one(
        "stock.location",
        string="Source Location",
        required=True,
        domain="[('usage', '=', 'internal'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    location_dest_id = fields.Many2one(
        "stock.location",
        string="Destination Location",
        required=True,
        domain="[('usage', '=', 'internal'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    scheduled_date = fields.Datetime(required=True, default=fields.Datetime.now)
    company_id = fields.Many2one(
        "res.company", related="request_order_id.company_id", readonly=True
    )

    @api.model
    def default_get(self, field_list):
        values = super().default_get(field_list)
        request = self.env["stock.request.order"].browse(
            values.get("request_order_id")
            or self.env.context.get("default_request_order_id")
        )
        if request:
            values.setdefault("picking_type_id", request.warehouse_id.int_type_id.id)
            values.setdefault("location_id", request.warehouse_id.lot_stock_id.id)
            if request.location_id != request.warehouse_id.lot_stock_id:
                values.setdefault("location_dest_id", request.location_id.id)
            values.setdefault("scheduled_date", request.expected_date)
        return values

    @api.constrains("location_id", "location_dest_id")
    def _check_locations(self):
        for wizard in self:
            if wizard.location_id == wizard.location_dest_id:
                raise ValidationError(
                    _("Source and destination locations must be different.")
                )

    def action_create_internal_transfer(self):
        self.ensure_one()
        if not self.env.user.has_group("stock.group_stock_user"):
            raise AccessError(_("Only an Inventory user can create a transfer."))
        request = self.request_order_id
        request._check_fulfillment_creation()
        if self.location_id == self.location_dest_id:
            raise UserError(_("Source and destination locations must be different."))

        moves = [
            (
                0,
                0,
                {
                    "name": line.request_reason or line.product_id.display_name,
                    "product_id": line.product_id.id,
                    "product_uom_qty": line.product_uom_qty,
                    "product_uom": line.product_uom_id.id,
                    "location_id": self.location_id.id,
                    "location_dest_id": self.location_dest_id.id,
                    "company_id": request.company_id.id,
                },
            )
            for line in request.stock_request_ids
        ]
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_id.id,
                "location_id": self.location_id.id,
                "location_dest_id": self.location_dest_id.id,
                "scheduled_date": self.scheduled_date,
                "origin": request.name,
                "company_id": request.company_id.id,
                "move_ids_without_package": moves,
            }
        )
        picking.action_confirm()
        request.write(
            {
                "generated_picking_ids": [(4, picking.id)],
                "state": "done",
            }
        )
        request.message_post(
            body=_(
                "Internal Transfer %(transfer)s created from this Material Requisition.",
                transfer=picking.display_name,
            ),
            subtype_xmlid="mail.mt_note",
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Internal Transfer"),
            "res_model": "stock.picking",
            "view_mode": "form",
            "res_id": picking.id,
        }
