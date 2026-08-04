from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


APPROVAL_STATES = [
    ("draft", "Not Requested"),
    ("waiting_level_1", "Waiting Level 1"),
    ("waiting_level_2", "Waiting Level 2"),
    ("waiting_level_3", "Waiting Level 3"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
]


PROTECTED_APPROVAL_FIELDS = {
    "approval_required",
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
    "approval_requested_by",
    "approval_requested_date",
}


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    approval_required = fields.Boolean(copy=False, readonly=True, tracking=True)
    approval_config_id = fields.Many2one(
        "legacy.purchase.approval.config",
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
    approval_requested_by = fields.Many2one(
        "res.users", copy=False, readonly=True, tracking=True
    )
    approval_requested_date = fields.Datetime(copy=False, readonly=True)
    current_approver_id = fields.Many2one(
        "res.users", compute="_compute_current_approver", string="Current Approver"
    )
    can_current_user_approve = fields.Boolean(compute="_compute_current_approver")

    @api.depends(
        "approval_state",
        "current_approval_level",
        "level_1_approver_id",
        "level_2_approver_id",
        "level_3_approver_id",
    )
    @api.depends_context("uid")
    def _compute_current_approver(self):
        level_fields = {
            1: "level_1_approver_id",
            2: "level_2_approver_id",
            3: "level_3_approver_id",
        }
        for order in self:
            approver = order[level_fields[order.current_approval_level]] if order.current_approval_level in level_fields else self.env["res.users"]
            order.current_approver_id = approver
            order.can_current_user_approve = bool(
                approver
                and approver == self.env.user
                and order.approval_state == f"waiting_level_{order.current_approval_level}"
            )

    def write(self, vals):
        if (
            PROTECTED_APPROVAL_FIELDS.intersection(vals)
            and not self.env.context.get("legacy_purchase_approval_internal")
        ):
            raise AccessError(
                _("Purchase approval fields can only be changed through approval actions.")
            )
        return super().write(vals)

    def _approval_write(self, values):
        return self.with_context(legacy_purchase_approval_internal=True).write(values)

    def _find_approval_config(self):
        self.ensure_one()
        configurations = self.env["legacy.purchase.approval.config"].search(
            [("company_id", "=", self.company_id.id), ("active", "=", True)],
            order="sequence, id",
        )
        return configurations.filtered(lambda config: config.matches_purchase_order(self))[:1]

    def _require_purchase_user(self):
        if not self.env.user.has_group("purchase.group_purchase_user"):
            raise AccessError(_("Only Purchase users can request purchase approval."))

    def action_request_approval(self):
        self.ensure_one()
        self._require_purchase_user()
        if self.state not in ("draft", "sent"):
            raise UserError(_("Approval can only be requested for an RFQ."))
        if self.approval_state != "draft":
            raise UserError(_("Purchase approval has already been requested."))
        config = self._find_approval_config()
        if not config:
            raise UserError(
                _(
                    "No purchase approval configuration found for this purchase order. "
                    "Please configure approval settings before requesting approval."
                )
            )
        now = fields.Datetime.now()
        self._approval_write(
            {
                "approval_required": True,
                "approval_config_id": config.id,
                "approval_state": "waiting_level_1",
                "current_approval_level": 1,
                "level_1_approver_id": config.level_1_approver_id.id,
                "level_2_approver_id": config.level_2_approver_id.id,
                "level_3_approver_id": config.level_3_approver_id.id,
                "approval_requested_by": self.env.user.id,
                "approval_requested_date": now,
                "rejection_reason": False,
                "rejected_by_id": False,
                "rejected_date": False,
            }
        )
        self.message_post(
            body=_(
                "Purchase approval requested by %(requester)s using configuration %(config)s.",
                requester=self.env.user.display_name,
                config=config.display_name,
            ),
            subtype_xmlid="mail.mt_note",
        )
        self._send_current_approver_request()
        return True

    def _check_current_approver(self):
        self.ensure_one()
        expected_state = f"waiting_level_{self.current_approval_level}"
        if (
            not self.current_approver_id
            or self.approval_state != expected_state
            or self.current_approver_id != self.env.user
        ):
            raise AccessError(
                _("Only the configured approver for the current level can perform this action.")
            )

    def action_approve_purchase(self):
        self.ensure_one()
        self._check_current_approver()
        level = self.current_approval_level
        now = fields.Datetime.now()
        self._approval_write(
            {
                f"level_{level}_approved_by": self.env.user.id,
                f"level_{level}_approved_date": now,
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
        next_approver = self[f"level_{next_level}_approver_id"] if next_level <= 3 else self.env["res.users"]
        if next_approver:
            self._approval_write(
                {
                    "approval_state": f"waiting_level_{next_level}",
                    "current_approval_level": next_level,
                }
            )
            self._send_current_approver_request()
        else:
            self._approval_write(
                {"approval_state": "approved", "current_approval_level": 0}
            )
            self.message_post(
                body=_("Purchase approval completed."),
                subtype_xmlid="mail.mt_note",
            )
            self._send_requester_result("legacy_purchase_approval.mail_template_purchase_approved")
        return True

    def action_open_rejection_wizard(self):
        self.ensure_one()
        self._check_current_approver()
        return {
            "type": "ir.actions.act_window",
            "name": _("Reject Purchase Order"),
            "res_model": "legacy.purchase.rejection.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_purchase_order_id": self.id},
        }

    def _apply_rejection(self, reason):
        self.ensure_one()
        self._check_current_approver()
        reason = (reason or "").strip()
        if not reason:
            raise UserError(_("A rejection reason is required."))
        level = self.current_approval_level
        rejecting_user = self.env.user
        self._approval_write(
            {
                "approval_state": "rejected",
                "current_approval_level": 0,
                "rejection_reason": reason,
                "rejected_by_id": rejecting_user.id,
                "rejected_date": fields.Datetime.now(),
            }
        )
        self.message_post(
            body=_(
                "Purchase Order rejected at Level %(level)s by %(approver)s. Reason: %(reason)s",
                level=level,
                approver=rejecting_user.display_name,
                reason=reason,
            ),
            subtype_xmlid="mail.mt_note",
        )
        self._send_requester_result("legacy_purchase_approval.mail_template_purchase_rejected")
        return True

    def action_reset_purchase_approval(self):
        self.ensure_one()
        if not self.env.user.has_group("purchase.group_purchase_manager"):
            raise AccessError(_("Only a Purchase Manager can reset a rejected approval."))
        if self.approval_state != "rejected":
            raise UserError(_("Only a rejected Purchase Order can be reset."))
        self._approval_write(
            {
                "approval_required": False,
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
                "approval_requested_by": False,
                "approval_requested_date": False,
            }
        )
        self.message_post(
            body=_("Rejected purchase approval reset by %s.", self.env.user.display_name),
            subtype_xmlid="mail.mt_note",
        )
        return True

    def _send_current_approver_request(self):
        self.ensure_one()
        approver = self.current_approver_id
        self._send_approval_email(
            "legacy_purchase_approval.mail_template_purchase_approval_request",
            approver,
        )
        self.message_post(
            body=_(
                "Approval request email queued for %(approver)s (Level %(level)s).",
                approver=approver.display_name,
                level=self.current_approval_level,
            ),
            subtype_xmlid="mail.mt_note",
        )

    def _send_requester_result(self, template_xmlid):
        self.ensure_one()
        requester = self.approval_requested_by
        self._send_approval_email(template_xmlid, requester)
        self.message_post(
            body=_("Approval result email queued for %s.", requester.display_name),
            subtype_xmlid="mail.mt_note",
        )

    def _send_approval_email(self, template_xmlid, recipient):
        self.ensure_one()
        if not recipient or not recipient.partner_id.email:
            raise UserError(
                _(
                    "An email address is required for approval user %s.",
                    recipient.display_name if recipient else _("(not configured)"),
                )
            )
        template = self.env.ref(template_xmlid)
        return template.sudo().send_mail(
            self.id,
            force_send=False,
            email_values={"recipient_ids": [(4, recipient.partner_id.id)]},
        )

    def button_confirm(self):
        for order in self:
            if order.approval_state == "rejected":
                raise UserError(
                    _("This Purchase Order has been rejected and cannot be confirmed.")
                )
            if order.approval_required and order.approval_state != "approved":
                raise UserError(
                    _(
                        "This Purchase Order cannot be confirmed because purchase approval "
                        "is still pending."
                    )
                )
        return super().button_confirm()
