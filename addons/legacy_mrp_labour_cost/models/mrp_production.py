from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import format_amount


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    labour_cost_line_ids = fields.One2many(
        "mrp.production.labour.cost",
        "production_id",
        string="Labour Costs",
        copy=False,
    )
    labour_line_count = fields.Integer(compute="_compute_labour_totals", store=True)
    labour_total_headcount = fields.Integer(compute="_compute_labour_totals", store=True)
    labour_total_hours = fields.Float(
        compute="_compute_labour_totals", store=True, digits=(16, 2)
    )
    labour_total_cost = fields.Monetary(
        compute="_compute_labour_totals", store=True, currency_field="company_currency_id"
    )
    labour_posted_cost = fields.Monetary(
        compute="_compute_labour_totals", store=True, currency_field="company_currency_id"
    )
    labour_unposted_cost = fields.Monetary(
        compute="_compute_labour_totals", store=True, currency_field="company_currency_id"
    )
    labour_reversed_cost = fields.Monetary(
        compute="_compute_labour_totals", store=True, currency_field="company_currency_id"
    )
    company_currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", readonly=True
    )
    labour_account_move_ids = fields.One2many(
        "account.move", "labour_production_id", string="Labour Journal Entries"
    )
    labour_journal_entry_count = fields.Integer(
        compute="_compute_labour_journal_entry_count"
    )

    @api.model_create_multi
    def create(self, values_list):
        productions = super().create(values_list)
        for production in productions:
            production._sync_labour_from_bom(update_existing=False)
        return productions

    def write(self, values):
        result = super().write(values)
        if "bom_id" in values and not self.env.context.get("skip_bom_labour_sync"):
            for production in self.filtered(lambda mo: mo.state == "draft"):
                obsolete = production.labour_cost_line_ids.filtered(
                    lambda line: line.posting_state == "draft"
                    and line.bom_labour_line_id
                    and line.bom_labour_line_id.bom_id != production.bom_id
                )
                obsolete.unlink()
                production._sync_labour_from_bom(update_existing=False)
        return result

    @api.onchange("bom_id")
    def _onchange_labour_cost_from_bom(self):
        for production in self:
            if production.state != "draft" or production.bom_id == production._origin.bom_id:
                continue
            manual_lines = production.labour_cost_line_ids.filtered(
                lambda line: not line.bom_labour_line_id
            )
            generated_lines = self.env["mrp.production.labour.cost"]
            for bom_line in production.bom_id.labour_preset_line_ids:
                generated_lines |= self.env["mrp.production.labour.cost"].new(
                    bom_line._prepare_production_labour_values(production)
                )
            production.labour_cost_line_ids = manual_lines | generated_lines

    def _sync_labour_from_bom(self, update_existing=True):
        """Load the BoM snapshot without duplicating lines or touching manual entries."""
        LabourLine = self.env["mrp.production.labour.cost"]
        for production in self:
            if production.state != "draft" or not production.bom_id:
                continue
            configured_lines = production.bom_id.labour_preset_line_ids
            existing_by_source = {
                line.bom_labour_line_id.id: line
                for line in production.labour_cost_line_ids
                if line.bom_labour_line_id
            }
            for bom_line in configured_lines:
                values = bom_line._prepare_production_labour_values(production)
                existing = existing_by_source.get(bom_line.id)
                if existing and update_existing:
                    values.pop("production_id", None)
                    values.pop("bom_labour_line_id", None)
                    existing.write(values)
                elif not existing:
                    LabourLine.create(values)
        return True

    def action_load_labour_from_bom(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("BoM labour presets can only be refreshed on a draft Manufacturing Order."))
        if not self.bom_id:
            raise UserError(_("Select a Bill of Materials first."))
        self._sync_labour_from_bom(update_existing=True)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Labour Presets Loaded"),
                "message": _("Labour lines were refreshed from %s.", self.bom_id.display_name),
                "type": "success",
                "sticky": False,
            },
        }

    @api.depends(
        "labour_cost_line_ids",
        "labour_cost_line_ids.labour_count",
        "labour_cost_line_ids.total_hours",
        "labour_cost_line_ids.total_cost",
        "labour_cost_line_ids.posting_state",
    )
    def _compute_labour_totals(self):
        for production in self:
            lines = production.labour_cost_line_ids
            production.labour_line_count = len(lines)
            production.labour_total_headcount = sum(lines.mapped("labour_count"))
            production.labour_total_hours = sum(lines.mapped("total_hours"))
            production.labour_total_cost = sum(lines.mapped("total_cost"))
            production.labour_posted_cost = sum(
                lines.filtered(lambda line: line.posting_state == "posted").mapped("total_cost")
            )
            production.labour_unposted_cost = sum(
                lines.filtered(lambda line: line.posting_state == "draft").mapped("total_cost")
            )
            production.labour_reversed_cost = sum(
                lines.filtered(lambda line: line.posting_state == "reversed").mapped("total_cost")
            )

    @api.depends("labour_account_move_ids")
    def _compute_labour_journal_entry_count(self):
        for production in self:
            production.labour_journal_entry_count = len(production.labour_account_move_ids)

    def _check_labour_posting_access(self):
        if not self.env.user.has_group("mrp.group_mrp_manager"):
            raise AccessError(_("Only a Manufacturing Manager can post labour costs."))
        if not self.env.user.has_group("account.group_account_user"):
            raise AccessError(
                _("Accounting Bookkeeper access is also required to post labour costs.")
            )

    def _validate_labour_accounting_configuration(self):
        self.ensure_one()
        company = self.company_id
        journal = company.manufacturing_labour_journal_id
        debit_account = company.manufacturing_labour_debit_account_id
        credit_account = company.manufacturing_labour_credit_account_id
        if not journal:
            raise UserError(_("Configure the Manufacturing Labour Journal first."))
        if not debit_account:
            raise UserError(_("Configure the Manufacturing Labour Debit Account first."))
        if not credit_account:
            raise UserError(_("Configure the Manufacturing Labour Credit Account first."))
        if journal.company_id != company or journal.type != "general":
            raise UserError(_("The labour journal must be a General journal for the Manufacturing Order company."))
        if debit_account.company_id != company or credit_account.company_id != company:
            raise UserError(_("Both labour accounts must belong to the Manufacturing Order company."))
        if debit_account.deprecated or credit_account.deprecated:
            raise UserError(_("The configured labour accounts must be active."))
        return journal, debit_account, credit_account

    def action_post_labour_cost(self):
        self.ensure_one()
        self._check_labour_posting_access()
        if self.state in ("draft", "cancel"):
            raise UserError(
                _("Labour costs cannot be posted for a draft or cancelled Manufacturing Order.")
            )
        draft_lines = self.labour_cost_line_ids.filtered(
            lambda line: line.posting_state == "draft"
        )
        if not draft_lines:
            raise UserError(_("There are no unposted labour costs to post."))
        zero_lines = draft_lines.filtered(lambda line: line.total_cost <= 0)
        if zero_lines:
            raise UserError(
                _("Every labour line being posted must have a positive Total Labour Cost.")
            )
        journal, debit_account, credit_account = self._validate_labour_accounting_configuration()
        posting_date = fields.Date.context_today(self)
        total = sum(draft_lines.mapped("total_cost"))
        move_lines = []
        for line in draft_lines:
            label = _(
                "Labour - %(workcenter)s - %(production)s",
                workcenter=line.workcenter_id.display_name,
                production=self.name,
            )
            if line.description:
                label = _("%(label)s - %(description)s", label=label, description=line.description)
            move_lines.append(
                (0, 0, {"name": label, "account_id": debit_account.id, "debit": line.total_cost, "credit": 0.0})
            )
        move_lines.append(
            (
                0,
                0,
                {
                    "name": _("Labour Clearing - %s", self.name),
                    "account_id": credit_account.id,
                    "debit": 0.0,
                    "credit": total,
                },
            )
        )
        move = (
            self.env["account.move"]
            .with_company(self.company_id)
            .create(
                {
                    "move_type": "entry",
                    "journal_id": journal.id,
                    "date": posting_date,
                    "ref": _("Labour Cost - %s", self.name),
                    "labour_production_id": self.id,
                    "line_ids": move_lines,
                }
            )
        )
        move.action_post()
        draft_lines._accounting_write(
            {
                "posting_state": "posted",
                "account_move_id": move.id,
                "posting_date": move.date,
                "posted_by_id": self.env.user.id,
            }
        )
        amount = format_amount(self.env, total, self.company_currency_id)
        self.message_post(
            body=_(
                "Labour cost of %(amount)s was posted by %(user)s through Journal Entry %(entry)s.",
                amount=amount,
                user=self.env.user.display_name,
                entry=move.display_name,
            ),
            subtype_xmlid="mail.mt_note",
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Labour Cost Posted"),
                "message": _("Journal Entry %s was posted.", move.display_name),
                "type": "success",
                "sticky": False,
            },
        }

    def action_view_labour_journal_entries(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Labour Journal Entries"),
            "res_model": "account.move",
            "view_mode": "tree,form",
            "domain": [("labour_production_id", "=", self.id)],
            "context": {"create": False, "default_move_type": "entry"},
        }
        if len(self.labour_account_move_ids) == 1:
            action.update({"view_mode": "form", "res_id": self.labour_account_move_ids.id})
        return action

    def action_open_labour_reversal_wizard(self):
        self.ensure_one()
        if not self.env.user.has_group("account.group_account_manager"):
            raise AccessError(_("Only an Accounting Manager can reverse labour costs."))
        posted_moves = self.labour_cost_line_ids.filtered(
            lambda line: line.posting_state == "posted"
        ).mapped("account_move_id")
        if not posted_moves:
            raise UserError(_("There are no posted labour costs to reverse."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Reverse Labour Cost"),
            "res_model": "mrp.labour.cost.reversal.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_production_id": self.id,
                "default_move_id": posted_moves.sorted("date", reverse=True)[:1].id,
            },
        }
