# Copyright 2017-2020 ForgeFlow, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_compare


APPROVAL_STATES = [
    ("draft", "Not Requested"),
    ("waiting_level_1", "Waiting Level 1"),
    ("waiting_level_2", "Waiting Level 2"),
    ("waiting_level_3", "Waiting Level 3"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
]

APPROVAL_STATUSES = [
    ("not_requested", "Not Requested"),
    ("requested", "Approval Requested"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
]

APPROVAL_ACTIVITY_SUMMARY = "Stock Request Approval Required"

PROTECTED_APPROVAL_FIELDS = {
    "approval_config_id",
    "approval_state",
    "current_approval_level",
    "level_1_approver_id",
    "level_2_approver_id",
    "level_3_approver_id",
    "level_1_approved_by",
    "level_2_approved_by",
    "level_3_approved_by",
    "level_1_approved_date",
    "level_2_approved_date",
    "level_3_approved_date",
    "rejection_reason",
    "rejected_by_id",
    "rejected_date",
    "approval_requested_date",
}


class StockRequest(models.Model):
    _name = "stock.request"
    _description = "Stock Request"
    _inherit = "stock.request.abstract"
    _order = "id desc"

    def _get_default_requested_by(self):
        return self.env["res.users"].browse(self.env.uid)

    @staticmethod
    def _get_expected_date():
        return fields.Datetime.now()

    name = fields.Char()
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("open", "Pending Approval"),
            ("done", "Approved"),
            ("rejected", "Rejected"),
            ("cancel", "Cancelled"),
        ],
        string="Status",
        copy=False,
        default="draft",
        index=True,
        readonly=True,
        tracking=True,
    )
    requested_by = fields.Many2one(
        "res.users",
        string="Requester",
        required=True,
        tracking=True,
        default=lambda s: s._get_default_requested_by(),
    )
    request_reason = fields.Text(string="Reason for Request", tracking=True)
    estimated_unit_cost = fields.Monetary(
        string="Cost",
        currency_field="currency_id",
        help="Estimated unit cost entered for approval and budgeting purposes.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Analytic Account",
        check_company=True,
    )
    approval_config_id = fields.Many2one(
        "stock.request.approval.config",
        string="Approval Matrix",
        copy=False,
        readonly=True,
        check_company=True,
        ondelete="restrict",
        tracking=True,
    )
    approval_state = fields.Selection(
        APPROVAL_STATES,
        required=True,
        default="draft",
        copy=False,
        readonly=True,
        tracking=True,
        index=True,
    )
    approval_status = fields.Selection(
        APPROVAL_STATUSES,
        compute="_compute_approval_status",
        store=True,
        index=True,
    )
    current_approval_level = fields.Integer(copy=False, readonly=True, tracking=True)
    level_1_approver_id = fields.Many2one(
        "res.users", copy=False, readonly=True, tracking=True
    )
    level_2_approver_id = fields.Many2one(
        "res.users", copy=False, readonly=True, tracking=True
    )
    level_3_approver_id = fields.Many2one(
        "res.users", copy=False, readonly=True, tracking=True
    )
    level_1_approved_by = fields.Many2one(
        "res.users", copy=False, readonly=True, tracking=True
    )
    level_2_approved_by = fields.Many2one(
        "res.users", copy=False, readonly=True, tracking=True
    )
    level_3_approved_by = fields.Many2one(
        "res.users", copy=False, readonly=True, tracking=True
    )
    level_1_approved_date = fields.Datetime(copy=False, readonly=True)
    level_2_approved_date = fields.Datetime(copy=False, readonly=True)
    level_3_approved_date = fields.Datetime(copy=False, readonly=True)
    rejection_reason = fields.Text(copy=False, readonly=True, tracking=True)
    rejected_by_id = fields.Many2one(
        "res.users", string="Rejected By", copy=False, readonly=True, tracking=True
    )
    rejected_date = fields.Datetime(copy=False, readonly=True)
    approval_requested_date = fields.Datetime(copy=False, readonly=True)
    current_approver_id = fields.Many2one(
        "res.users",
        compute="_compute_current_approver_id",
        store=True,
        string="Current Approver",
    )
    can_current_user_approve = fields.Boolean(compute="_compute_can_current_user_approve")
    expected_date = fields.Datetime(
        index=True,
        required=True,
        help="Date when you expect to receive the goods.",
    )
    picking_policy = fields.Selection(
        [
            ("direct", "Receive each product when available"),
            ("one", "Receive all products at once"),
        ],
        string="Shipping Policy",
        required=True,
        default="direct",
    )
    move_ids = fields.One2many(
        comodel_name="stock.move",
        compute="_compute_move_ids",
        string="Stock Moves",
        readonly=True,
    )
    picking_ids = fields.One2many(
        "stock.picking",
        compute="_compute_picking_ids",
        string="Pickings",
        readonly=True,
    )
    qty_in_progress = fields.Float(
        digits="Product Unit of Measure",
        readonly=True,
        compute="_compute_qty",
        store=True,
        help="Quantity in progress.",
    )
    qty_done = fields.Float(
        digits="Product Unit of Measure",
        readonly=True,
        compute="_compute_qty",
        store=True,
        help="Quantity completed",
    )
    qty_cancelled = fields.Float(
        digits="Product Unit of Measure",
        readonly=True,
        compute="_compute_qty",
        store=True,
        help="Quantity cancelled",
    )
    picking_count = fields.Integer(
        string="Delivery Orders",
        compute="_compute_picking_ids",
        readonly=True,
    )
    allocation_ids = fields.One2many(
        comodel_name="stock.request.allocation",
        inverse_name="stock_request_id",
        string="Stock Request Allocation",
    )
    order_id = fields.Many2one("stock.request.order", readonly=True)
    warehouse_id = fields.Many2one()
    location_id = fields.Many2one()
    product_id = fields.Many2one()
    product_uom_id = fields.Many2one()
    product_uom_qty = fields.Float()
    procurement_group_id = fields.Many2one()
    company_id = fields.Many2one()
    route_id = fields.Many2one()

    _sql_constraints = [
        ("name_uniq", "unique(name, company_id)", "Stock Request name must be unique")
    ]

    @api.depends("approval_state")
    def _compute_approval_status(self):
        for request in self:
            if (request.approval_state or "").startswith("waiting_level_"):
                request.approval_status = "requested"
            elif request.approval_state in ("approved", "rejected"):
                request.approval_status = request.approval_state
            else:
                request.approval_status = "not_requested"

    @api.depends(
        "approval_state",
        "current_approval_level",
        "level_1_approver_id",
        "level_2_approver_id",
        "level_3_approver_id",
    )
    def _compute_current_approver_id(self):
        level_fields = {
            1: "level_1_approver_id",
            2: "level_2_approver_id",
            3: "level_3_approver_id",
        }
        for request in self:
            field_name = level_fields.get(request.current_approval_level)
            approver = request[field_name] if field_name else self.env["res.users"]
            request.current_approver_id = approver

    @api.depends("approval_state", "current_approver_id")
    @api.depends_context("uid")
    def _compute_can_current_user_approve(self):
        for request in self:
            approver = request.current_approver_id
            request.can_current_user_approve = bool(
                approver
                and approver == self.env.user
                and request.approval_state
                == f"waiting_level_{request.current_approval_level}"
            )

    def write(self, vals):
        if (
            PROTECTED_APPROVAL_FIELDS.intersection(vals)
            and not self.env.context.get("stock_request_approval_internal")
        ):
            raise AccessError(
                _("Stock Request approval fields can only be changed by approval actions.")
            )
        return super().write(vals)

    def _approval_write(self, values):
        return self.with_context(stock_request_approval_internal=True).write(values)

    def _find_approval_config(self):
        self.ensure_one()
        configs = self.env["stock.request.approval.config"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("active", "=", True),
                "|",
                ("requester_id", "=", self.requested_by.id),
                ("requester_id", "=", False),
            ],
            order="sequence, id",
        )
        return (
            configs.filtered(lambda config: config.requester_id == self.requested_by)[:1]
            or configs.filtered(lambda config: not config.requester_id)[:1]
        )

    @api.constrains("state", "product_qty")
    def _check_qty(self):
        for rec in self:
            if rec.state == "draft" and rec.product_qty <= 0:
                raise ValidationError(
                    _("Stock Request product quantity has to be strictly positive.")
                )
            elif rec.state != "draft" and rec.product_qty < 0:
                raise ValidationError(
                    _("Stock Request product quantity cannot be negative.")
                )

    def _get_all_origin_moves(self, move):
        all_moves = move
        if move.move_orig_ids:
            for orig_move in move.move_orig_ids:
                all_moves |= self._get_all_origin_moves(orig_move)
        return all_moves

    @api.depends("allocation_ids", "allocation_ids.stock_move_id")
    def _compute_move_ids(self):
        for request in self:
            move_ids = request.allocation_ids.mapped("stock_move_id")
            all_moves = self.env["stock.move"]
            for move in move_ids:
                all_moves |= self._get_all_origin_moves(move)
            request.move_ids = all_moves

    @api.depends(
        "allocation_ids",
        "allocation_ids.stock_move_id",
        "allocation_ids.stock_move_id.picking_id",
    )
    def _compute_picking_ids(self):
        for request in self:
            request.picking_count = 0
            request.picking_ids = self.env["stock.picking"]
            request.picking_ids = request.move_ids.filtered(
                lambda m: m.state != "cancel"
            ).mapped("picking_id")
            request.picking_count = len(request.picking_ids)

    @api.depends(
        "allocation_ids",
        "allocation_ids.stock_move_id.state",
        "allocation_ids.stock_move_id.move_line_ids",
        "allocation_ids.stock_move_id.move_line_ids.quantity",
    )
    def _compute_qty(self):
        for request in self:
            incoming_qty = 0.0
            other_qty = 0.0
            for allocation in request.allocation_ids:
                if allocation.stock_move_id.picking_code == "incoming":
                    incoming_qty += allocation.allocated_product_qty
                else:
                    other_qty += allocation.allocated_product_qty
            done_qty = abs(other_qty - incoming_qty)
            open_qty = sum(request.allocation_ids.mapped("open_product_qty"))
            uom = request.product_id.uom_id
            request.qty_done = uom._compute_quantity(
                done_qty,
                request.product_uom_id,
                rounding_method="HALF-UP",
            )
            request.qty_in_progress = uom._compute_quantity(
                open_qty,
                request.product_uom_id,
                rounding_method="HALF-UP",
            )
            request.qty_cancelled = (
                max(
                    0,
                    uom._compute_quantity(
                        request.product_qty - done_qty - open_qty,
                        request.product_uom_id,
                        rounding_method="HALF-UP",
                    ),
                )
                if request.allocation_ids
                else 0
            )

    @api.constrains("order_id", "requested_by")
    def check_order_requested_by(self):
        check_order_requested_by = (
            self.env.company.stock_request_check_order_requested_by
        )
        if not check_order_requested_by:
            return
        for stock_request in self:
            if (
                stock_request.order_id
                and stock_request.order_id.requested_by != stock_request.requested_by
            ):
                raise ValidationError(_("Requested by must be equal to the order"))

    @api.constrains("order_id", "warehouse_id")
    def check_order_warehouse_id(self):
        for stock_request in self:
            if (
                stock_request.order_id
                and stock_request.order_id.warehouse_id != stock_request.warehouse_id
            ):
                raise ValidationError(_("Warehouse must be equal to the order"))

    @api.constrains("order_id", "location_id")
    def check_order_location(self):
        for stock_request in self:
            if (
                stock_request.order_id
                and stock_request.order_id.location_id != stock_request.location_id
            ):
                raise ValidationError(_("Location must be equal to the order"))

    @api.constrains("order_id", "procurement_group_id")
    def check_order_procurement_group(self):
        for stock_request in self:
            if (
                stock_request.order_id
                and stock_request.order_id.procurement_group_id
                != stock_request.procurement_group_id
            ):
                raise ValidationError(_("Procurement group must be equal to the order"))

    @api.constrains("order_id", "company_id")
    def check_order_company(self):
        for stock_request in self:
            if (
                stock_request.order_id
                and stock_request.order_id.company_id != stock_request.company_id
            ):
                raise ValidationError(_("Company must be equal to the order"))

    @api.constrains("order_id", "expected_date")
    def check_order_expected_date(self):
        for stock_request in self:
            if (
                stock_request.order_id
                and stock_request.order_id.expected_date != stock_request.expected_date
            ):
                raise ValidationError(_("Expected date must be equal to the order"))

    @api.constrains("order_id", "picking_policy")
    def check_order_picking_policy(self):
        for stock_request in self:
            if (
                stock_request.order_id
                and stock_request.order_id.picking_policy
                != stock_request.picking_policy
            ):
                raise ValidationError(
                    _("The picking policy must be equal to the order")
                )

    def action_request_approval(self):
        for request in self:
            if request.state != "draft" or request.approval_state != "draft":
                raise UserError(_("Approval can only be requested from Draft status."))
            if (
                request.requested_by != self.env.user
                and not self.env.user.has_group(
                    "stock_request.group_stock_request_manager"
                )
            ):
                raise AccessError(
                    _("Only the requester or a Stock Request Manager can submit this request.")
                )
            config = request._find_approval_config()
            if not config:
                raise UserError(
                    _(
                        "No Stock Request approval matrix is configured for %(requester)s. "
                        "Ask a Stock Request Manager to configure one first.",
                        requester=request.requested_by.display_name,
                    )
                )
            request._approval_write(
                {
                    "state": "open",
                    "approval_config_id": config.id,
                    "approval_state": "waiting_level_1",
                    "current_approval_level": 1,
                    "level_1_approver_id": config.level_1_approver_id.id,
                    "level_2_approver_id": config.level_2_approver_id.id,
                    "level_3_approver_id": config.level_3_approver_id.id,
                    "approval_requested_date": fields.Datetime.now(),
                    "rejection_reason": False,
                    "rejected_by_id": False,
                    "rejected_date": False,
                }
            )
            request.message_post(
                body=_(
                    "Approval requested by %(requester)s using matrix %(matrix)s.",
                    requester=request.requested_by.display_name,
                    matrix=config.display_name,
                ),
                subtype_xmlid="mail.mt_note",
            )
            request._notify_current_approver()
        return True

    def _action_confirm(self):
        return self.action_request_approval()

    def action_confirm(self):
        return self.action_request_approval()

    def _check_current_approver(self):
        self.ensure_one()
        if (
            not self.current_approver_id
            or self.current_approver_id != self.env.user
            or self.approval_state
            != f"waiting_level_{self.current_approval_level}"
        ):
            raise AccessError(
                _("Only the configured approver for the current level can act on this request.")
            )

    def action_approve_request(self):
        self.ensure_one()
        self._check_current_approver()
        level = self.current_approval_level
        self._complete_current_approval_activity(
            _(
                "Level %(level)s approved by %(approver)s.",
                level=level,
                approver=self.env.user.display_name,
            )
        )
        self._approval_write(
            {
                f"level_{level}_approved_by": self.env.user.id,
                f"level_{level}_approved_date": fields.Datetime.now(),
            }
        )
        self.message_post(
            body=_(
                "Level %(level)s approved by %(approver)s.",
                level=level,
                approver=self.env.user.display_name,
            ),
            subtype_xmlid="mail.mt_note",
        )
        next_level = level + 1
        next_approver = (
            self[f"level_{next_level}_approver_id"]
            if next_level <= 3
            else self.env["res.users"]
        )
        if next_approver:
            self._approval_write(
                {
                    "approval_state": f"waiting_level_{next_level}",
                    "current_approval_level": next_level,
                }
            )
            self._notify_current_approver()
        else:
            self._approval_write(
                {
                    "state": "done",
                    "approval_state": "approved",
                    "current_approval_level": 0,
                }
            )
            self.message_post(
                body=_("Stock Request approval completed."),
                subtype_xmlid="mail.mt_note",
            )
            self._notify_requester(
                _("Stock Request Approved: %s", self.name),
                _("Stock Request %s has completed the approval workflow.", self.name),
            )
        return True

    def action_open_rejection_wizard(self):
        self.ensure_one()
        self._check_current_approver()
        return {
            "type": "ir.actions.act_window",
            "name": _("Reject Stock Request"),
            "res_model": "stock.request.rejection.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_stock_request_id": self.id},
        }

    def _apply_rejection(self, reason):
        self.ensure_one()
        self._check_current_approver()
        reason = (reason or "").strip()
        if not reason:
            raise UserError(_("A rejection reason is required."))
        level = self.current_approval_level
        self._complete_current_approval_activity(
            _(
                "Level %(level)s rejected by %(approver)s.",
                level=level,
                approver=self.env.user.display_name,
            )
        )
        self._approval_write(
            {
                "state": "rejected",
                "approval_state": "rejected",
                "current_approval_level": 0,
                "rejection_reason": reason,
                "rejected_by_id": self.env.user.id,
                "rejected_date": fields.Datetime.now(),
            }
        )
        self.message_post(
            body=_(
                "Stock Request rejected at Level %(level)s by %(approver)s. "
                "Reason: %(reason)s",
                level=level,
                approver=self.env.user.display_name,
                reason=reason,
            ),
            subtype_xmlid="mail.mt_note",
        )
        self._notify_requester(
            _("Stock Request Rejected: %s", self.name),
            _("Stock Request %(request)s was rejected. Reason: %(reason)s", request=self.name, reason=reason),
        )
        return True

    def action_reset_request_approval(self):
        self.ensure_one()
        if not self.env.user.has_group("stock_request.group_stock_request_manager"):
            raise AccessError(_("Only a Stock Request Manager can reset a rejection."))
        if self.approval_state != "rejected":
            raise UserError(_("Only a rejected Stock Request can be reset."))
        self._approval_write(
            {
                "state": "draft",
                "approval_config_id": False,
                "approval_state": "draft",
                "current_approval_level": 0,
                "level_1_approver_id": False,
                "level_2_approver_id": False,
                "level_3_approver_id": False,
                "level_1_approved_by": False,
                "level_2_approved_by": False,
                "level_3_approved_by": False,
                "level_1_approved_date": False,
                "level_2_approved_date": False,
                "level_3_approved_date": False,
                "rejection_reason": False,
                "rejected_by_id": False,
                "rejected_date": False,
                "approval_requested_date": False,
            }
        )
        self.message_post(
            body=_("Rejected Stock Request reset by %s.", self.env.user.display_name),
            subtype_xmlid="mail.mt_note",
        )
        return True

    def _notify_current_approver(self):
        self.ensure_one()
        approver = self.current_approver_id
        self._notify_user(
            approver,
            _("Stock Request Approval Required: %s", self.name),
            _(
                "Stock Request %(request)s requires your Level %(level)s approval.",
                request=self.name,
                level=self.current_approval_level,
            ),
        )
        existing = self.activity_ids.filtered(
            lambda activity: activity.user_id == approver
            and activity.summary == APPROVAL_ACTIVITY_SUMMARY
        )
        if not existing:
            self.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=approver.id,
                summary=APPROVAL_ACTIVITY_SUMMARY,
                note=_(
                    "Review Stock Request %(request)s and approve or reject Level %(level)s.",
                    request=self.name,
                    level=self.current_approval_level,
                ),
            )

    def _notify_requester(self, subject, body):
        self.ensure_one()
        self._notify_user(self.requested_by, subject, body)

    def _notify_user(self, recipient, subject, body):
        self.ensure_one()
        if recipient and recipient.partner_id:
            self.message_notify(
                subject=subject,
                body=body,
                partner_ids=[recipient.partner_id.id],
                subtype_xmlid="mail.mt_note",
            )

    def _complete_current_approval_activity(self, feedback):
        self.ensure_one()
        activities = self.activity_ids.filtered(
            lambda activity: activity.user_id == self.env.user
            and activity.summary == APPROVAL_ACTIVITY_SUMMARY
        )
        if activities:
            activities.action_feedback(feedback=feedback)

    def action_draft(self):
        self.write({"state": "draft"})
        return True

    def action_cancel(self):
        self.sudo().mapped("move_ids")._action_cancel()
        self.activity_ids.filtered(
            lambda activity: activity.summary == APPROVAL_ACTIVITY_SUMMARY
        ).sudo().unlink()
        self._approval_write(
            {
                "state": "cancel",
                "approval_state": "draft",
                "current_approval_level": 0,
            }
        )
        return True

    def action_done(self):
        self.write({"state": "done"})
        return True

    def check_cancel(self):
        for request in self:
            if request._check_cancel_allocation():
                request.write({"state": "cancel"})

    def check_done(self):
        precision = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        for request in self:
            allocated_qty = sum(request.allocation_ids.mapped("allocated_product_qty"))
            qty_done = request.product_id.uom_id._compute_quantity(
                allocated_qty, request.product_uom_id
            )
            if (
                float_compare(
                    qty_done, request.product_uom_qty, precision_digits=precision
                )
                >= 0
            ):
                request.action_done()
            elif request._check_cancel_allocation():
                # If qty_done=0 and qty_cancelled>0 it's cancelled
                request.write({"state": "cancel"})
        return True

    def _check_cancel_allocation(self):
        precision = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        self.ensure_one()
        return (
            self.allocation_ids
            and float_compare(self.qty_cancelled, 0, precision_digits=precision) > 0
        )

    def _prepare_procurement_values(self, group_id=False):
        """Prepare specific key for moves or other components that
        will be created from a procurement rule
        coming from a stock request. This method could be override
        in order to add other custom key that could be used in
        move/po creation.
        """
        return {
            "date_planned": self.expected_date,
            "warehouse_id": self.warehouse_id,
            "stock_request_allocation_ids": self.id,
            "group_id": group_id or self.procurement_group_id.id or False,
            "route_ids": self.route_id,
            "stock_request_id": self.id,
        }

    def _skip_procurement(self):
        return self.state != "draft" or self.product_id.type not in ("consu", "product")

    def _prepare_stock_move(self, qty):
        return {
            "name": self.product_id.display_name,
            "company_id": self.company_id.id,
            "product_id": self.product_id.id,
            "product_uom_qty": qty,
            "product_uom": self.product_id.uom_id.id,
            "location_id": self.location_id.id,
            "location_dest_id": self.location_id.id,
            "state": "draft",
            "reference": self.name,
        }

    def _prepare_stock_request_allocation(self, move):
        return {
            "stock_request_id": self.id,
            "stock_move_id": move.id,
            "requested_product_uom_qty": move.product_uom_qty,
        }

    def _action_use_stock_available(self):
        """Create a stock move with the necessary data and mark it as done."""
        allocation_model = self.env["stock.request.allocation"]
        stock_move_model = self.env["stock.move"].sudo()
        precision = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        quants = self.env["stock.quant"]._gather(self.product_id, self.location_id)
        pending_qty = self.product_uom_qty
        for quant in quants.filtered(lambda x: x.available_quantity >= 0):
            qty_move = min(pending_qty, quant.available_quantity)
            if float_compare(qty_move, 0, precision_digits=precision) > 0:
                move = stock_move_model.create(self._prepare_stock_move(qty_move))
                move._action_confirm()
                pending_qty -= qty_move
                # Create allocation + done move
                allocation_model.create(self._prepare_stock_request_allocation(move))
                move.quantity = move.product_uom_qty
                move.picked = True
                move._action_done()

    def _action_launch_procurement_rule(self):
        """
        Launch procurement group (if not enough stock is available) run method
        with required/custom fields genrated by a
        stock request. procurement group will launch '_run_move',
        '_run_buy' or '_run_manufacture'
        depending on the stock request product rule.
        """
        precision = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        errors = []
        for request in self:
            if request._skip_procurement():
                continue
            qty = 0.0
            for move in request.move_ids.filtered(lambda r: r.state != "cancel"):
                qty += move.product_qty

            if float_compare(qty, request.product_qty, precision_digits=precision) >= 0:
                continue

            # If stock is available we use it and we do not execute rule
            if request.company_id.stock_request_check_available_first:
                if (
                    float_compare(
                        request.product_id.sudo()
                        .with_context(location=request.location_id.id)
                        .free_qty,
                        request.product_uom_qty,
                        precision_digits=precision,
                    )
                    >= 0
                ):
                    request._action_use_stock_available()
                    continue

            values = request._prepare_procurement_values(
                group_id=request.procurement_group_id
            )
            try:
                procurements = []
                procurements.append(
                    self.env["procurement.group"].Procurement(
                        request.product_id,
                        request.product_uom_qty,
                        request.product_uom_id,
                        request.location_id,
                        request.name,
                        request.name,
                        self.env.company,
                        values,
                    )
                )
                self.env["procurement.group"].run(procurements)
            except UserError as error:
                errors.append(str(error))
        if errors:
            raise UserError("\n".join(errors))
        return True

    def action_view_transfer(self):
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "stock.action_picking_tree_all"
        )
        pickings = self.mapped("picking_ids")
        if len(pickings) > 1:
            action["domain"] = [("id", "in", pickings.ids)]
        elif pickings:
            action["views"] = [(self.env.ref("stock.view_picking_form").id, "form")]
            action["res_id"] = pickings.id
        return action

    @api.model_create_multi
    def create(self, vals_list):
        vals_list_upd = []
        for vals in vals_list:
            upd_vals = vals.copy()
            if upd_vals.get("name", "/") == "/":
                upd_vals["name"] = self.env["ir.sequence"].next_by_code("stock.request")
            if "order_id" in upd_vals:
                order_id = self.env["stock.request.order"].browse(upd_vals["order_id"])
                upd_vals["expected_date"] = order_id.expected_date
            else:
                upd_vals["expected_date"] = self._get_expected_date()
            vals_list_upd.append(upd_vals)
        return super().create(vals_list_upd)

    def unlink(self):
        if self.filtered(lambda r: r.state != "draft"):
            raise UserError(_("Only requests on draft state can be unlinked"))
        return super().unlink()
