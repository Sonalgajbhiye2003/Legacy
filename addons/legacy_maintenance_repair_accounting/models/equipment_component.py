from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


COMPONENT_STATUS_SELECTION = [
    ("planned", "Planned"),
    ("installed", "Installed"),
    ("under_repair", "Under Repair"),
    ("removed", "Removed"),
    ("recycled", "Recycled"),
    ("scrapped", "Scrapped"),
]


class MaintenanceEquipmentComponent(models.Model):
    _name = "maintenance.equipment.component"
    _description = "Maintenance Equipment Component"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _parent_store = True
    _order = "equipment_id, parent_path, id"

    name = fields.Char(string="Component Name", required=True, tracking=True, index="trigram")
    equipment_id = fields.Many2one(
        "maintenance.equipment",
        required=True,
        index=True,
        ondelete="restrict",
        check_company=True,
        tracking=True,
    )
    parent_id = fields.Many2one(
        "maintenance.equipment.component",
        string="Parent Component",
        index=True,
        ondelete="restrict",
        check_company=True,
        tracking=True,
    )
    parent_path = fields.Char(index=True, unaccent=False)
    child_ids = fields.One2many("maintenance.equipment.component", "parent_id", string="Child Components")
    product_id = fields.Many2one(
        "product.product",
        required=True,
        check_company=True,
        tracking=True,
        domain="[('type', 'in', ('product', 'consu')), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    description = fields.Text()
    quantity = fields.Float(required=True, default=1.0, digits="Product Unit of Measure", tracking=True)
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        required=True,
        domain="[('category_id', '=', product_uom_category_id)]",
    )
    product_uom_category_id = fields.Many2one(related="product_id.uom_id.category_id")
    lot_id = fields.Many2one(
        "stock.lot",
        string="Lot/Serial Number",
        check_company=True,
        domain="[('product_id', '=', product_id), ('company_id', '=', company_id)]",
        tracking=True,
    )
    manufacturer = fields.Char()
    model = fields.Char(string="Model")
    installed_date = fields.Date(tracking=True)
    removed_date = fields.Date(tracking=True)
    warranty_expiry = fields.Date(tracking=True)
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    installation_cost = fields.Monetary(currency_field="currency_id", tracking=True)
    status = fields.Selection(COMPONENT_STATUS_SELECTION, required=True, default="planned", tracking=True, index=True)
    installed_repair_order_id = fields.Many2one(
        "repair.order", string="Installed by Repair/Build Order", check_company=True, ondelete="restrict", tracking=True
    )
    removed_repair_order_id = fields.Many2one(
        "repair.order", string="Removed by Repair Order", check_company=True, ondelete="restrict", tracking=True
    )
    installation_move_id = fields.Many2one(
        "stock.move", string="Installation Stock Move", check_company=True, ondelete="restrict", tracking=True
    )
    removal_move_id = fields.Many2one(
        "stock.move", string="Removal Stock Move", check_company=True, ondelete="restrict", tracking=True
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    active = fields.Boolean(default=True)
    notes = fields.Text()
    history_ids = fields.One2many("maintenance.equipment.component.event", "component_id", string="History")

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for component in self:
            if component.product_id:
                component.name = component.name or component.product_id.display_name
                component.uom_id = component.product_id.uom_id
                if component.lot_id.product_id != component.product_id:
                    component.lot_id = False

    @api.constrains("parent_id")
    def _check_parent_recursion(self):
        if not self._check_recursion():
            raise ValidationError(_("A component cannot be a parent of itself or one of its ancestors."))

    @api.constrains("equipment_id", "parent_id", "company_id", "product_id", "uom_id", "quantity", "lot_id", "status")
    def _check_component_integrity(self):
        installed_statuses = ("installed", "under_repair")
        for component in self:
            if float_compare(component.quantity, 0.0, precision_rounding=component.uom_id.rounding) <= 0:
                raise ValidationError(_("Component quantity must be greater than zero."))
            if component.uom_id.category_id != component.product_id.uom_id.category_id:
                raise ValidationError(_("Component and product Units of Measure must belong to the same category."))
            if component.equipment_id.company_id and component.equipment_id.company_id != component.company_id:
                raise ValidationError(_("Equipment and component must belong to the same company."))
            if component.parent_id and (
                component.parent_id.company_id != component.company_id
                or component.parent_id.equipment_id != component.equipment_id
            ):
                raise ValidationError(_("Parent and child components must belong to the same equipment and company."))
            if component.lot_id and component.product_id.tracking == "serial" and float_compare(
                component.quantity, 1.0, precision_rounding=component.uom_id.rounding
            ) != 0:
                raise ValidationError(_("A serial-tracked installed component must have quantity 1."))
            if component.lot_id and component.status in installed_statuses:
                duplicate = self.search_count(
                    [
                        ("id", "!=", component.id),
                        ("lot_id", "=", component.lot_id.id),
                        ("status", "in", installed_statuses),
                        ("company_id", "=", component.company_id.id),
                    ],
                    limit=1,
                )
                if duplicate:
                    raise ValidationError(_("This lot/serial number is already installed on equipment."))

    def _record_event(self, from_status, to_status, repair_order=None, stock_move=None, notes=None):
        self.ensure_one()
        return self.env["maintenance.equipment.component.event"].create(
            {
                "component_id": self.id,
                "from_status": from_status,
                "to_status": to_status,
                "event_date": fields.Datetime.now(),
                "repair_order_id": repair_order.id if repair_order else False,
                "stock_move_id": stock_move.id if stock_move else False,
                "user_id": self.env.user.id,
                "company_id": self.company_id.id,
                "notes": notes,
            }
        )

    def _transition(self, target, allowed, repair_order=None, stock_move=None, values=None, notes=None):
        self.ensure_one()
        if self.status == target:
            return self
        if self.status not in allowed:
            raise UserError(_("Component %(component)s cannot move from %(from_state)s to %(to_state)s.", component=self.display_name, from_state=self.status, to_state=target))
        from_status = self.status
        write_values = dict(values or {}, status=target)
        self.write(write_values)
        self._record_event(from_status, target, repair_order=repair_order, stock_move=stock_move, notes=notes)
        return self

    def action_install_component(self, repair_order=None, stock_move=None, installed_date=None, notes=None):
        self.ensure_one()
        values = {
            "installed_date": installed_date or fields.Date.context_today(self),
            "removed_date": False,
            "installed_repair_order_id": repair_order.id if repair_order else self.installed_repair_order_id.id,
            "installation_move_id": stock_move.id if stock_move else self.installation_move_id.id,
        }
        return self._transition("installed", ("planned", "removed"), repair_order, stock_move, values, notes)

    def action_remove_component(self, repair_order=None, stock_move=None, removed_date=None, notes=None):
        self.ensure_one()
        values = {
            "removed_date": removed_date or fields.Date.context_today(self),
            "removed_repair_order_id": repair_order.id if repair_order else self.removed_repair_order_id.id,
            "removal_move_id": stock_move.id if stock_move else self.removal_move_id.id,
        }
        return self._transition("removed", ("installed", "under_repair"), repair_order, stock_move, values, notes)

    def action_send_for_repair(self, repair_order=None, notes=None):
        return self._transition("under_repair", ("installed",), repair_order=repair_order, notes=notes)

    def action_recycle_component(self, repair_order=None, stock_move=None, notes=None):
        return self._transition("recycled", ("removed", "under_repair"), repair_order, stock_move, notes=notes)

    def action_scrap_component(self, repair_order=None, stock_move=None, notes=None):
        return self._transition("scrapped", ("installed", "removed", "under_repair"), repair_order, stock_move, notes=notes)

    def action_replace_component(self, replacement, repair_order=None, removal_move=None, installation_move=None, notes=None):
        self.ensure_one()
        replacement.ensure_one()
        if replacement == self or replacement.equipment_id != self.equipment_id:
            raise UserError(_("Replacement must be a different component on the same equipment."))
        self.action_remove_component(repair_order, removal_move, notes=notes)
        replacement.action_install_component(repair_order, installation_move, notes=notes)
        return replacement


class MaintenanceEquipmentComponentEvent(models.Model):
    _name = "maintenance.equipment.component.event"
    _description = "Equipment Component History"
    _order = "event_date desc, id desc"

    component_id = fields.Many2one("maintenance.equipment.component", required=True, index=True, ondelete="restrict", check_company=True)
    equipment_id = fields.Many2one(related="component_id.equipment_id", store=True, index=True)
    from_status = fields.Selection(COMPONENT_STATUS_SELECTION)
    to_status = fields.Selection(COMPONENT_STATUS_SELECTION, required=True)
    event_date = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    repair_order_id = fields.Many2one("repair.order", check_company=True, ondelete="restrict")
    stock_move_id = fields.Many2one("stock.move", check_company=True, ondelete="restrict")
    user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
    company_id = fields.Many2one("res.company", required=True, index=True)
    notes = fields.Text()

    def write(self, values):
        if not self.env.context.get("legacy_component_history_correction"):
            raise UserError(_("Component history is immutable."))
        return super().write(values)

    def unlink(self):
        raise UserError(_("Component history cannot be deleted."))


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    legacy_component_ids = fields.One2many("maintenance.equipment.component", "equipment_id", string="Components")
    legacy_component_count = fields.Integer(compute="_compute_legacy_equipment_counts")
    legacy_component_history_count = fields.Integer(compute="_compute_legacy_equipment_counts")
    legacy_repair_order_count = fields.Integer(compute="_compute_legacy_equipment_counts")
    legacy_material_request_count = fields.Integer(compute="_compute_legacy_equipment_counts")
    legacy_journal_entry_count = fields.Integer(compute="_compute_legacy_equipment_counts")

    def _compute_legacy_equipment_counts(self):
        for equipment in self:
            equipment.legacy_component_count = self.env["maintenance.equipment.component"].search_count([("equipment_id", "=", equipment.id), ("active", "=", True)])
            equipment.legacy_component_history_count = self.env["maintenance.equipment.component.event"].search_count([("equipment_id", "=", equipment.id)])
            equipment.legacy_repair_order_count = self.env["repair.order"].search_count([("legacy_equipment_id", "=", equipment.id)])
            equipment.legacy_material_request_count = self.env["stock.request.order"].search_count([("legacy_equipment_id", "=", equipment.id)])
            equipment.legacy_journal_entry_count = self.env["account.move"].search_count([("legacy_equipment_id", "=", equipment.id)])

    def _legacy_equipment_action(self, xmlid, domain):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(xmlid)
        action["domain"] = domain
        return action

    def action_view_legacy_component_history(self):
        return self._legacy_equipment_action("legacy_maintenance_repair_accounting.action_equipment_component_history", [("equipment_id", "=", self.id)])

    def action_view_legacy_repair_orders(self):
        return self._legacy_equipment_action("repair.action_repair_order_tree", [("legacy_equipment_id", "=", self.id)])

    def action_view_legacy_material_requests(self):
        return self._legacy_equipment_action("stock_request.stock_request_order_action", [("legacy_equipment_id", "=", self.id)])

    def action_view_legacy_journal_entries(self):
        return self._legacy_equipment_action("account.action_move_journal_line", [("legacy_equipment_id", "=", self.id)])


class RepairOrder(models.Model):
    _inherit = "repair.order"

    legacy_installed_component_ids = fields.One2many("maintenance.equipment.component", "installed_repair_order_id", string="Installed Components")
    legacy_removed_component_ids = fields.One2many("maintenance.equipment.component", "removed_repair_order_id", string="Removed Components")
    legacy_component_count = fields.Integer(compute="_compute_legacy_component_count")

    @api.depends("legacy_installed_component_ids", "legacy_removed_component_ids")
    def _compute_legacy_component_count(self):
        for order in self:
            order.legacy_component_count = len(order.legacy_installed_component_ids | order.legacy_removed_component_ids)
