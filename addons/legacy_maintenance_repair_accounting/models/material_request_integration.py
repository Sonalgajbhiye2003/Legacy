from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare

from .common import ACCOUNTING_STATUS_SELECTION, EXPENSE_TYPE_SELECTION, FINANCE_APPROVAL_SELECTION


class StockRequestOrder(models.Model):
    _inherit = "stock.request.order"

    legacy_request_purpose = fields.Selection(
        [("repair", "Repair Existing Machine"), ("build", "Build New Machine")],
        string="Request Purpose",
        index=True,
    )
    legacy_default_expense_type = fields.Selection(EXPENSE_TYPE_SELECTION, string="Default CAPEX/OPEX")
    legacy_finance_approval_state = fields.Selection(
        FINANCE_APPROVAL_SELECTION,
        string="Finance Approval",
        required=True,
        default="draft",
        tracking=True,
        copy=False,
    )
    legacy_total_issued_value = fields.Monetary(compute="_compute_legacy_material_totals", currency_field="currency_id")
    legacy_accounting_status = fields.Selection(
        ACCOUNTING_STATUS_SELECTION,
        string="Accounting Status",
        required=True,
        default="not_posted",
        tracking=True,
        copy=False,
    )
    legacy_journal_entry_count = fields.Integer(compute="_compute_legacy_material_totals")

    @api.depends("stock_request_ids.legacy_posted_value", "stock_request_ids.legacy_journal_entry_id")
    def _compute_legacy_material_totals(self):
        for request in self:
            request.legacy_total_issued_value = sum(request.stock_request_ids.mapped("legacy_posted_value"))
            request.legacy_journal_entry_count = len(request.stock_request_ids.mapped("legacy_journal_entry_id"))

    def action_submit_legacy_finance(self):
        for request in self:
            lines = request.stock_request_ids.filtered(lambda line: line.legacy_fulfillment_owner == "repair")
            if not lines:
                raise UserError(_("This action applies only to Repair/Build material lines."))
            lines.write({"legacy_finance_approval_state": "pending"})
            request.legacy_finance_approval_state = "pending"
        return True

    def action_approve_legacy_finance(self):
        if not self.env.user.has_group("legacy_maintenance_repair_accounting.group_finance_maintenance_approver"):
            raise AccessError(_("Only a Maintenance CAPEX/OPEX Approver can approve material classification."))
        for request in self:
            lines = request.stock_request_ids.filtered(lambda line: line.legacy_fulfillment_owner == "repair")
            if not lines:
                raise UserError(_("No Repair-owned material lines were found."))
            for line in lines:
                line.action_approve_legacy_finance()
            request.legacy_finance_approval_state = "approved"
        return True

    def action_reserve_legacy_repair_materials(self):
        for request in self:
            if request.state != "approved":
                raise UserError(_("Material Requisition must be approved before reservation."))
            lines = request.stock_request_ids.filtered(lambda line: line.legacy_fulfillment_owner == "repair")
            if any(line.legacy_finance_approval_state != "approved" for line in lines):
                raise UserError(_("Finance must approve every Repair-owned material line before reservation."))
            for order in lines.mapped("legacy_repair_order_id"):
                if order.state == "draft":
                    order.action_validate()
                order.action_assign()
        return True


class StockRequest(models.Model):
    _inherit = "stock.request"

    legacy_repair_order_id = fields.Many2one("repair.order", string="Repair/Build Order", index=True, ondelete="restrict", check_company=True)
    legacy_repair_move_id = fields.Many2one("stock.move", string="Repair Part Move", index=True, ondelete="restrict", check_company=True)
    legacy_operation_id = fields.Many2one("legacy.repair.operation", string="Operation", index=True, ondelete="restrict", check_company=True)
    legacy_equipment_id = fields.Many2one("maintenance.equipment", string="Equipment", index=True, check_company=True)
    legacy_workcenter_id = fields.Many2one("mrp.workcenter", string="Work Centre", check_company=True)
    legacy_expense_type = fields.Selection(EXPENSE_TYPE_SELECTION, string="CAPEX/OPEX", tracking=True)
    legacy_debit_account_id = fields.Many2one("account.account", string="Approved Debit Account", check_company=True, copy=False)
    legacy_finance_approval_state = fields.Selection(
        FINANCE_APPROVAL_SELECTION,
        string="Finance Approval",
        required=True,
        default="draft",
        tracking=True,
        copy=False,
    )
    legacy_approved_quantity = fields.Float(digits="Product Unit of Measure", copy=False)
    legacy_available_quantity = fields.Float(compute="_compute_legacy_fulfillment_quantities", digits="Product Unit of Measure")
    legacy_consumed_quantity = fields.Float(compute="_compute_legacy_fulfillment_quantities", digits="Product Unit of Measure")
    legacy_returned_quantity = fields.Float(compute="_compute_legacy_fulfillment_quantities", digits="Product Unit of Measure")
    legacy_posted_value = fields.Monetary(compute="_compute_legacy_fulfillment_quantities", currency_field="currency_id")
    legacy_journal_entry_id = fields.Many2one("account.move", check_company=True, copy=False, readonly=True, ondelete="restrict")
    legacy_return_entry_id = fields.Many2one("account.move", check_company=True, copy=False, readonly=True, ondelete="restrict")
    legacy_fulfillment_owner = fields.Selection(
        [("material_request", "Material Requisition"), ("repair", "Repair Order")],
        string="Fulfilment Owner",
        required=True,
        default="material_request",
        index=True,
    )
    legacy_purchase_line_ids = fields.One2many("purchase.order.line", "legacy_stock_request_line_id", string="Purchase Lines")
    legacy_receipt_move_ids = fields.One2many("stock.move", "legacy_stock_request_line_id", string="Receipt/Related Moves")

    @api.depends(
        "legacy_repair_move_id.state",
        "legacy_repair_move_id.quantity",
        "legacy_repair_move_id.stock_valuation_layer_ids.value",
        "legacy_repair_move_id.returned_move_ids.state",
        "legacy_repair_move_id.returned_move_ids.quantity",
        "product_id",
        "warehouse_id",
    )
    def _compute_legacy_fulfillment_quantities(self):
        for line in self:
            move = line.legacy_repair_move_id
            line.legacy_consumed_quantity = move.quantity if move.state == "done" else 0.0
            return_moves = move.returned_move_ids.filtered(lambda item: item.state == "done" and item.legacy_stock_request_line_id == line)
            line.legacy_returned_quantity = sum(return_moves.mapped("quantity"))
            line.legacy_posted_value = abs(sum(move.stock_valuation_layer_ids.mapped("value"))) if move.state == "done" else 0.0
            location = line.warehouse_id.lot_stock_id
            line.legacy_available_quantity = self.env["stock.quant"]._get_available_quantity(line.product_id, location) if line.product_id and location else 0.0

    @api.constrains("legacy_repair_order_id", "legacy_repair_move_id", "legacy_operation_id", "company_id")
    def _check_legacy_repair_material_links(self):
        for line in self.filtered(lambda item: item.legacy_fulfillment_owner == "repair"):
            if not line.legacy_repair_order_id or not line.legacy_repair_move_id:
                raise ValidationError(_("Repair-owned material lines require a Repair/Build Order and Repair Part move."))
            if line.legacy_repair_move_id.repair_id != line.legacy_repair_order_id:
                raise ValidationError(_("Repair Part move and Repair/Build Order do not match."))
            if line.legacy_operation_id and line.legacy_operation_id.repair_order_id != line.legacy_repair_order_id:
                raise ValidationError(_("Operation and Repair/Build Order do not match."))

    def action_approve_legacy_finance(self):
        if not self.env.user.has_group("legacy_maintenance_repair_accounting.group_finance_maintenance_approver"):
            raise AccessError(_("Only a Maintenance CAPEX/OPEX Approver can approve material classification."))
        for line in self:
            if line.legacy_fulfillment_owner != "repair":
                continue
            if not line.legacy_expense_type:
                raise ValidationError(_("CAPEX/OPEX classification is required."))
            automated = line.product_id.valuation == "real_time"
            config = line.company_id._legacy_check_material_configuration(line.legacy_expense_type, automated=automated)
            move = line.legacy_repair_move_id
            if move.state not in ("draft", "confirmed", "waiting"):
                raise UserError(_("Material classification must be approved before the Repair Part is reserved or consumed."))
            move.write(
                {
                    "location_dest_id": config["location"].id,
                    "legacy_expense_type": line.legacy_expense_type,
                    "legacy_stock_request_line_id": line.id,
                    "legacy_operation_id": line.legacy_operation_id.id,
                    "legacy_equipment_id": line.legacy_equipment_id.id,
                    "legacy_workcenter_id": line.legacy_workcenter_id.id,
                }
            )
            line.write(
                {
                    "legacy_debit_account_id": config["debit_account"].id,
                    "legacy_approved_quantity": line.legacy_approved_quantity or line.product_uom_qty,
                    "legacy_finance_approval_state": "approved",
                }
            )
        return True

    def action_create_legacy_return(self):
        self.ensure_one()
        original = self.legacy_repair_move_id
        if original.state != "done":
            raise UserError(_("Only consumed material can be returned."))
        returned = self.legacy_returned_quantity
        quantity = self.legacy_consumed_quantity - returned
        if float_compare(quantity, 0.0, precision_rounding=self.product_uom_id.rounding) <= 0:
            existing = original.returned_move_ids.filtered(lambda move: move.legacy_stock_request_line_id == self and move.state != "cancel")
            return existing[:1]
        return_move = self.env["stock.move"].create(
            {
                "name": _("Return of %(move)s", move=original.display_name),
                "product_id": original.product_id.id,
                "product_uom_qty": quantity,
                "product_uom": original.product_uom.id,
                "location_id": original.location_dest_id.id,
                "location_dest_id": original.location_id.id,
                "company_id": original.company_id.id,
                "origin_returned_move_id": original.id,
                "legacy_stock_request_line_id": self.id,
                "legacy_expense_type": self.legacy_expense_type,
                "legacy_equipment_id": self.legacy_equipment_id.id,
                "legacy_workcenter_id": self.legacy_workcenter_id.id,
            }
        )
        return_move._action_confirm()
        return_move.quantity = quantity
        return_move.picked = True
        return_move._action_done()
        self.order_id.message_post(body=_("Material %(product)s was returned against %(move)s.", product=self.product_id.display_name, move=original.display_name), subtype_xmlid="mail.mt_note")
        return return_move


class StockMove(models.Model):
    _inherit = "stock.move"

    legacy_request_material = fields.Boolean(string="Request Material", default=True)
    legacy_stock_request_line_id = fields.Many2one("stock.request", string="Material Requisition Line", index=True, ondelete="restrict", check_company=True)
    legacy_operation_id = fields.Many2one("legacy.repair.operation", string="Repair Operation", index=True, ondelete="restrict", check_company=True)
    legacy_equipment_id = fields.Many2one("maintenance.equipment", string="Equipment", index=True, check_company=True)
    legacy_workcenter_id = fields.Many2one("mrp.workcenter", string="Work Centre", check_company=True)
    legacy_equipment_component_id = fields.Many2one("maintenance.equipment.component", string="Equipment Component", ondelete="restrict", check_company=True)
    legacy_expense_type = fields.Selection(EXPENSE_TYPE_SELECTION, string="CAPEX/OPEX", index=True)


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    legacy_stock_request_line_id = fields.Many2one("stock.request", string="Material Requisition Line", index=True, ondelete="restrict", check_company=True)

    def _prepare_stock_moves(self, picking):
        values = super()._prepare_stock_moves(picking)
        if self.legacy_stock_request_line_id:
            for move_values in values:
                move_values["legacy_stock_request_line_id"] = self.legacy_stock_request_line_id.id
        return values


class StockRequestPurchaseWizard(models.TransientModel):
    _inherit = "stock.request.purchase.wizard"

    def action_create_purchase_order(self):
        self.ensure_one()
        request = self.request_order_id
        lines = request.stock_request_ids
        action = super().action_create_purchase_order()
        purchase = self.env["purchase.order"].browse(action.get("res_id"))
        for request_line, purchase_line in zip(lines, purchase.order_line):
            purchase_line.legacy_stock_request_line_id = request_line
        if request.legacy_repair_order_id:
            request.state = "approved"
        return action


class RepairOrder(models.Model):
    _inherit = "repair.order"

    def action_create_legacy_material_request(self):
        self.ensure_one()
        moves = self.move_ids.filtered(
            lambda move: move.repair_line_type == "add"
            and move.legacy_request_material
            and not move.legacy_stock_request_line_id
            and move.state != "cancel"
        )
        existing = self.move_ids.mapped("legacy_stock_request_line_id").filtered(lambda line: line.state != "cancel")
        if not moves:
            if existing:
                return existing[0].order_id.action_view_stock_requests()
            raise UserError(_("Select at least one unrequested Add part."))
        warehouse = self.env["stock.warehouse"].search([("company_id", "=", self.company_id.id)], limit=1)
        if not warehouse:
            raise UserError(_("Configure a warehouse for %(company)s first.", company=self.company_id.display_name))
        request = self.env["stock.request.order"].create(
            {
                "requested_by": self.env.user.id,
                "company_id": self.company_id.id,
                "warehouse_id": warehouse.id,
                "location_id": warehouse.lot_stock_id.id,
                "legacy_maintenance_request_id": self.legacy_maintenance_request_id.id,
                "legacy_repair_order_id": self.id,
                "legacy_equipment_id": self.legacy_equipment_id.id,
                "workcenter_id": (self.legacy_workcenter_id or self.legacy_target_workcenter_id).id,
                "legacy_request_purpose": self.legacy_order_type,
                "legacy_default_expense_type": self.legacy_proposed_expense_type,
                "expenditure_type": self.legacy_proposed_expense_type,
            }
        )
        for move in moves:
            line = self.env["stock.request"].create(
                {
                    "order_id": request.id,
                    "product_id": move.product_id.id,
                    "product_uom_qty": move.product_uom_qty,
                    "product_uom_id": move.product_uom.id,
                    "requested_by": self.env.user.id,
                    "company_id": self.company_id.id,
                    "warehouse_id": request.warehouse_id.id,
                    "location_id": request.location_id.id,
                    "expected_date": request.expected_date,
                    "legacy_repair_order_id": self.id,
                    "legacy_repair_move_id": move.id,
                    "legacy_operation_id": move.legacy_operation_id.id,
                    "legacy_equipment_id": self.legacy_equipment_id.id,
                    "legacy_workcenter_id": (self.legacy_workcenter_id or self.legacy_target_workcenter_id).id,
                    "legacy_expense_type": self.legacy_proposed_expense_type,
                    "legacy_fulfillment_owner": "repair",
                    "request_reason": move.name,
                }
            )
            move.legacy_stock_request_line_id = line
        self.message_post(body=_("Material Requisition %(request)s was created for selected Repair Parts.", request=request.display_name), subtype_xmlid="mail.mt_note")
        return {
            "type": "ir.actions.act_window",
            "name": _("Material Requisition"),
            "res_model": "stock.request.order",
            "view_mode": "form",
            "res_id": request.id,
        }

    def action_repair_done(self):
        for order in self:
            linked_add_moves = order.move_ids.filtered(lambda move: move.repair_line_type == "add" and move.state != "cancel")
            if any(not move.legacy_stock_request_line_id or move.legacy_stock_request_line_id.legacy_finance_approval_state != "approved" for move in linked_add_moves):
                raise UserError(_("Every Add Repair Part requires an approved Material Requisition line and Finance classification."))
        result = super().action_repair_done()
        for order in self:
            order._legacy_update_components_from_done_moves()
            requests = order.move_ids.mapped("legacy_stock_request_line_id.order_id")
            for request in requests:
                repair_moves = request.stock_request_ids.mapped("legacy_repair_move_id")
                if repair_moves and all(move.state in ("done", "cancel") for move in repair_moves):
                    request.state = "done"
        return result

    def _legacy_update_components_from_done_moves(self):
        for order in self:
            for move in order.move_ids.filtered(lambda item: item.state == "done"):
                component = move.legacy_equipment_component_id
                if move.repair_line_type == "add" and order.legacy_equipment_id and not component:
                    component = self.env["maintenance.equipment.component"].create(
                        {
                            "name": move.product_id.display_name,
                            "equipment_id": order.legacy_equipment_id.id,
                            "product_id": move.product_id.id,
                            "quantity": move.quantity,
                            "uom_id": move.product_uom.id,
                            "lot_id": move.lot_ids[:1].id,
                            "company_id": order.company_id.id,
                            "installation_cost": abs(sum(move.stock_valuation_layer_ids.mapped("value"))),
                        }
                    )
                    component.action_install_component(order, move)
                    move.legacy_equipment_component_id = component
                elif component and move.repair_line_type == "remove":
                    component.action_remove_component(order, move)
                elif component and move.repair_line_type == "recycle":
                    component.action_recycle_component(order, move)
