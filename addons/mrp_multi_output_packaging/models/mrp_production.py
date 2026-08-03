from collections import defaultdict

from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero

from .mrp_bom import PROCESS_SELECTION, WORKFLOW_SELECTION


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    manufacturing_workflow = fields.Selection(
        WORKFLOW_SELECTION, required=True, default="standard", copy=True, index=True
    )
    custom_process_type = fields.Selection(PROCESS_SELECTION, copy=True)
    output_line_ids = fields.One2many("mrp.production.output.line", "production_id", copy=True)
    recipe_snapshot_ids = fields.One2many("mrp.production.recipe.snapshot", "production_id", copy=False)
    packaging_line_ids = fields.One2many("mrp.production.packaging.line", "production_id", copy=False)

    bulk_product_id = fields.Many2one("product.product", check_company=True)
    planned_usable_output_qty = fields.Float(digits="Product Unit of Measure")
    actual_usable_output_qty = fields.Float(digits="Product Unit of Measure")
    bulk_uom_id = fields.Many2one("uom.uom")
    total_planned_packaged_equivalent = fields.Float(
        compute="_compute_reconciliation", store=True, digits="Product Unit of Measure"
    )
    total_actual_packaged_equivalent = fields.Float(
        compute="_compute_reconciliation", store=True, digits="Product Unit of Measure"
    )
    planned_process_loss_qty = fields.Float(digits="Product Unit of Measure")
    process_loss_qty = fields.Float(digits="Product Unit of Measure")
    remaining_bulk_qty = fields.Float(
        compute="_compute_reconciliation", store=True, digits="Product Unit of Measure"
    )
    expected_remaining_bulk_qty = fields.Float(
        compute="_compute_reconciliation", store=True, digits="Product Unit of Measure"
    )
    reconciliation_difference = fields.Float(
        compute="_compute_reconciliation", store=True, digits="Product Unit of Measure"
    )
    reconciliation_status = fields.Selection(
        [("balanced", "Balanced"), ("warning", "Warning"), ("blocked", "Blocked")],
        compute="_compute_reconciliation", store=True,
    )
    variance_reason = fields.Char()
    variance_approved = fields.Boolean(string="Variance Approved", copy=False)

    @api.depends(
        "output_line_ids.planned_qty", "output_line_ids.actual_qty",
        "output_line_ids.equivalent_bulk_qty", "output_line_ids.output_classification",
        "planned_usable_output_qty", "actual_usable_output_qty", "planned_process_loss_qty",
        "process_loss_qty", "company_id.quantity_warning_tolerance",
        "company_id.quantity_blocking_tolerance"
    )
    def _compute_reconciliation(self):
        for production in self:
            packaged = production.output_line_ids.filtered(
                lambda line: line.output_classification == "primary_packaged"
            )
            production.total_planned_packaged_equivalent = sum(
                line.planned_qty * line.net_content_qty and line.net_content_uom_id._compute_quantity(
                    line.planned_qty * line.net_content_qty, line.bulk_equivalent_product_id.uom_id
                ) or 0.0
                for line in packaged
                if line.net_content_uom_id and line.bulk_equivalent_product_id
                and line.net_content_uom_id.category_id == line.bulk_equivalent_product_id.uom_id.category_id
            )
            production.total_actual_packaged_equivalent = sum(
                line.actual_qty * line.net_content_qty and line.net_content_uom_id._compute_quantity(
                    line.actual_qty * line.net_content_qty, line.bulk_equivalent_product_id.uom_id
                ) or 0.0
                for line in packaged
                if line.net_content_uom_id and line.bulk_equivalent_product_id
                and line.net_content_uom_id.category_id == line.bulk_equivalent_product_id.uom_id.category_id
            )
            production.expected_remaining_bulk_qty = (
                production.planned_usable_output_qty
                - production.total_planned_packaged_equivalent
                - production.planned_process_loss_qty
            )
            production.remaining_bulk_qty = (
                production.actual_usable_output_qty
                - production.total_actual_packaged_equivalent
                - production.process_loss_qty
            )
            bulk_line = production.output_line_ids.filtered(
                lambda line: line.output_classification == "primary_bulk"
            )[:1]
            recorded_bulk = bulk_line.actual_qty if production.actual_usable_output_qty else bulk_line.planned_qty
            expected_bulk = production.remaining_bulk_qty if production.actual_usable_output_qty else production.expected_remaining_bulk_qty
            difference = expected_bulk - recorded_bulk
            production.reconciliation_difference = difference
            absolute = abs(difference)
            if absolute > production.company_id.quantity_blocking_tolerance:
                production.reconciliation_status = "blocked"
            elif absolute > production.company_id.quantity_warning_tolerance:
                production.reconciliation_status = "warning"
            else:
                production.reconciliation_status = "balanced"

    @api.onchange("bom_id")
    def _onchange_bom_multi_output(self):
        if self.bom_id:
            self.manufacturing_workflow = self.bom_id.manufacturing_workflow
            self.custom_process_type = self.bom_id.custom_process_type
            if self.manufacturing_workflow == "custom_multi_output":
                self.bulk_product_id = self.bom_id.product_id
                self.bulk_uom_id = self.bom_id.product_uom_id
                self.planned_usable_output_qty = self.product_qty
                self._ensure_default_packaged_output()

    @api.onchange("bulk_product_id")
    def _onchange_bulk_product_id(self):
        self.bulk_uom_id = self.bulk_product_id.uom_id

    @api.onchange(
        "planned_usable_output_qty", "actual_usable_output_qty", "planned_process_loss_qty",
        "process_loss_qty", "bulk_product_id", "output_line_ids"
    )
    def _onchange_sync_bulk_line(self):
        self._sync_primary_bulk_output_line()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("bom_id"):
                bom = self.env["mrp.bom"].browse(vals["bom_id"])
                vals.setdefault("manufacturing_workflow", bom.manufacturing_workflow)
                vals.setdefault("custom_process_type", bom.custom_process_type)
        productions = super().create(vals_list)
        if not self.env.context.get("skip_multi_output_sync"):
            productions._ensure_default_packaged_output()
            productions._sync_primary_bulk_output_line()
        return productions

    def write(self, vals):
        if {"manufacturing_workflow", "custom_process_type"} & set(vals):
            locked = self.filtered(lambda production: production.state != "draft")
            if locked:
                raise UserError("Manufacturing Workflow and Custom Process Type are locked after confirmation.")
        result = super().write(vals)
        if not self.env.context.get("skip_multi_output_sync") and {
            "planned_usable_output_qty", "actual_usable_output_qty", "planned_process_loss_qty",
            "process_loss_qty", "bulk_product_id"
        } & set(vals):
            self._sync_primary_bulk_output_line()
        return result

    @api.constrains("manufacturing_workflow", "custom_process_type", "bulk_product_id", "bulk_uom_id")
    def _check_custom_configuration(self):
        for production in self:
            if production.manufacturing_workflow == "standard":
                if production.custom_process_type:
                    raise ValidationError("Custom Process Type must be empty for a Standard Odoo MO.")
                continue
            if not production.custom_process_type:
                raise ValidationError("Custom Process Type is required for a Custom Multi-Output MO.")
            if production.custom_process_type == "integrated_production_packaging":
                if not production.bulk_product_id or not production.bulk_uom_id:
                    raise ValidationError("Bulk Product and Bulk UoM are required for integrated production and packaging.")
                if production.bulk_uom_id.category_id != production.bulk_product_id.uom_id.category_id:
                    raise ValidationError("Bulk Product and Bulk UoM are incompatible.")

    def _get_move_raw_values(self, product_id, product_uom_qty, product_uom, operation_id=False, bom_line=False):
        values = super()._get_move_raw_values(
            product_id, product_uom_qty, product_uom, operation_id=operation_id, bom_line=bom_line
        )
        values["component_source"] = "process_bom" if bom_line else "manual"
        return values

    def _ensure_default_packaged_output(self):
        """Add the BoM's packaged product when the user has not planned one."""
        Output = self.env["mrp.production.output.line"]
        for production in self.filtered(
            lambda mo: mo.manufacturing_workflow == "custom_multi_output"
            and mo.bom_id.default_packaged_product_id
        ):
            packaged = production.output_line_ids.filtered(
                lambda line: line.output_classification == "primary_packaged"
            )
            if packaged:
                continue

            product = production.bom_id.default_packaged_product_id
            recipe = product.packaging_recipe_id or self.env["mrp.packaging.recipe"].effective_recipe(
                product,
                production.company_id,
                fields.Date.to_date(production.date_start) if production.date_start else None,
            )
            if not recipe or not product.net_content_uom_id or not product.bulk_equivalent_product_id:
                continue
            bulk_uom = production.bulk_uom_id or production.bom_id.product_uom_id
            if product.net_content_uom_id.category_id != bulk_uom.category_id:
                continue
            content_per_unit = product.net_content_uom_id._compute_quantity(
                product.net_content_qty, bulk_uom
            )
            if float_is_zero(content_per_unit, precision_rounding=bulk_uom.rounding):
                continue
            bulk_qty = production.planned_usable_output_qty or production.product_qty
            values = {
                "product_id": product.id,
                "output_classification": "primary_packaged",
                "planned_qty": bulk_qty / content_per_unit,
                "actual_qty": 0.0,
                "product_uom_id": product.uom_id.id,
                "net_content_qty": product.net_content_qty,
                "net_content_uom_id": product.net_content_uom_id.id,
                "bulk_equivalent_product_id": product.bulk_equivalent_product_id.id,
                "packaging_recipe_id": recipe.id,
                "location_dest_id": production.location_dest_id.id,
            }
            if production._origin.id:
                values["production_id"] = production.id
                Output.with_context(skip_multi_output_sync=True).create(values)
            else:
                production.output_line_ids = [Command.create(values)]

    def _sync_primary_bulk_output_line(self):
        for production in self.filtered(
            lambda mo: mo.manufacturing_workflow == "custom_multi_output"
            and mo.custom_process_type == "integrated_production_packaging"
            and mo.bulk_product_id
        ):
            # Onchange records do not yet have a real production_id. Creating
            # the related output row here would violate its required Many2one.
            # ``create`` synchronizes the row immediately after the MO is saved.
            if not production._origin.id:
                continue
            packaged = production.output_line_ids.filtered(
                lambda line: line.output_classification == "primary_packaged"
            )
            planned_equivalent = sum(
                line.net_content_uom_id._compute_quantity(
                    line.planned_qty * line.net_content_qty, production.bulk_uom_id
                ) for line in packaged
                if line.net_content_uom_id and line.net_content_uom_id.category_id == production.bulk_uom_id.category_id
            )
            actual_equivalent = sum(
                line.net_content_uom_id._compute_quantity(
                    line.actual_qty * line.net_content_qty, production.bulk_uom_id
                ) for line in packaged
                if line.net_content_uom_id and line.net_content_uom_id.category_id == production.bulk_uom_id.category_id
            )
            planned_remaining = production.planned_usable_output_qty - planned_equivalent - production.planned_process_loss_qty
            actual_remaining = production.actual_usable_output_qty - actual_equivalent - production.process_loss_qty
            bulk_lines = production.output_line_ids.filtered(
                lambda line: line.output_classification == "primary_bulk"
            )
            values = {
                "product_id": production.bulk_product_id.id,
                "product_uom_id": production.bulk_uom_id.id,
                "planned_qty": max(planned_remaining, 0.0),
                "actual_qty": max(actual_remaining, 0.0) if production.actual_usable_output_qty else 0.0,
                "location_dest_id": production.location_dest_id.id,
                "output_classification": "primary_bulk",
            }
            if bulk_lines:
                bulk_lines[:1].with_context(skip_multi_output_sync=True).write(values)
                if len(bulk_lines) > 1:
                    bulk_lines[1:].with_context(skip_multi_output_sync=True).unlink()
            else:
                values["production_id"] = production.id
                self.env["mrp.production.output.line"].with_context(skip_multi_output_sync=True).create(values)

    def _validate_custom_output_plan(self, completion=False):
        for production in self.filtered(lambda mo: mo.manufacturing_workflow == "custom_multi_output"):
            packaged = production.output_line_ids.filtered(
                lambda line: line.output_classification == "primary_packaged"
            )
            if not packaged:
                raise UserError(
                    "No packaged product is configured for this BoM. "
                    "Ask a Manufacturing Manager to set the BoM's Packaged Product."
                )
            if len(production.output_line_ids.mapped("product_id")) != len(production.output_line_ids):
                raise UserError("Duplicate output products are not allowed.")
            for line in packaged:
                if not line.packaging_recipe_id:
                    raise UserError(_("Packaging Recipe is missing for %s.", line.product_id.display_name))
                if line.net_content_qty <= 0 or not line.net_content_uom_id:
                    raise UserError(_("Net Content is missing for %s.", line.product_id.display_name))
                if line.product_id.tracking != "none" and completion and not line.lot_id:
                    raise UserError(_("A Lot/Serial Number is required for %s.", line.product_id.display_name))
                overrun = line.actual_qty - line.planned_qty
                if completion and overrun > production.company_id.quantity_warning_tolerance and not production.variance_approved:
                    raise UserError("Actual output exceeds the planned tolerance and requires Supervisor approval.")
            if completion:
                if production.actual_usable_output_qty <= 0:
                    raise UserError("Actual Usable Output is required before completion.")
                if production.remaining_bulk_qty < -production.bulk_uom_id.rounding:
                    raise UserError("Remaining Bulk cannot be negative.")
                if production.reconciliation_status == "blocked":
                    raise UserError("Reconciliation difference exceeds the company blocking tolerance.")
                if production.reconciliation_status == "warning" and not production.variance_reason:
                    raise UserError("A Variance Reason is required for a reconciliation warning.")
                threshold = production.company_id.packaging_variance_reason_threshold
                for packaging in production.packaging_line_ids:
                    if abs(packaging.variance_qty) > threshold and not packaging.variance_reason:
                        raise UserError(_("A packaging variance reason is required for %s.", packaging.packaging_product_id.display_name))

    def _snapshot_packaging_recipes(self):
        Snapshot = self.env["mrp.production.recipe.snapshot"]
        for production in self:
            production.recipe_snapshot_ids.unlink()
            for output in production.output_line_ids.filtered(
                lambda line: line.output_classification == "primary_packaged"
            ):
                recipe = output.packaging_recipe_id
                snapshot = Snapshot.create({
                    "production_id": production.id,
                    "output_line_id": output.id,
                    "recipe_id": recipe.id,
                    "recipe_version": recipe.version,
                    "finished_product_id": output.product_id.id,
                    "base_qty": recipe.base_qty,
                    "base_uom_id": recipe.base_uom_id.id,
                    "line_ids": [(0, 0, {
                        "packaging_product_id": recipe_line.packaging_product_id.id,
                        "qty_per_unit": recipe_line.qty_per_base / recipe.base_qty,
                        "product_uom_id": recipe_line.product_uom_id.id,
                        "rounding_method": recipe_line.rounding_method,
                        "wastage_percentage": recipe_line.wastage_percentage,
                        "operation_id": (recipe_line.operation_id or recipe.operation_id or output.product_id.default_packaging_operation_id).id,
                        "workcenter_id": (recipe.workcenter_id or output.product_id.default_packaging_workcenter_id).id,
                        "allow_manual_adjustment": recipe_line.allow_manual_adjustment,
                        "sequence": recipe_line.sequence,
                    }) for recipe_line in recipe.line_ids],
                })
                output.packaging_recipe_version = snapshot.recipe_version

    def _rebuild_packaging_calculations(self):
        Calculation = self.env["mrp.production.packaging.line"]
        for production in self:
            production.packaging_line_ids.unlink()
            for snapshot in production.recipe_snapshot_ids:
                output = snapshot.output_line_id
                for snap_line in snapshot.line_ids:
                    planned = Calculation.calculate_requirement(
                        output.planned_qty, snap_line.qty_per_unit, snap_line.wastage_percentage,
                        snap_line.rounding_method, snap_line.product_uom_id,
                    )
                    expected_actual = Calculation.calculate_requirement(
                        output.actual_qty, snap_line.qty_per_unit, snap_line.wastage_percentage,
                        snap_line.rounding_method, snap_line.product_uom_id,
                    )
                    Calculation.create({
                        "production_id": production.id,
                        "output_line_id": output.id,
                        "recipe_snapshot_line_id": snap_line.id,
                        "finished_product_id": output.product_id.id,
                        "packaging_product_id": snap_line.packaging_product_id.id,
                        "qty_per_unit": snap_line.qty_per_unit,
                        "planned_output_qty": output.planned_qty,
                        "planned_packaging_qty": planned,
                        "actual_output_qty": output.actual_qty,
                        "expected_actual_packaging_qty": expected_actual,
                        "product_uom_id": snap_line.product_uom_id.id,
                        "rounding_method": snap_line.rounding_method,
                        "wastage_percentage": snap_line.wastage_percentage,
                        "operation_id": snap_line.operation_id.id,
                    })

    def _refresh_actual_packaging_calculations(self):
        Calculation = self.env["mrp.production.packaging.line"]
        for production in self:
            lines_by_move = defaultdict(lambda: self.env["mrp.production.packaging.line"])
            for line in production.packaging_line_ids:
                output = line.output_line_id
                expected = Calculation.calculate_requirement(
                    output.actual_qty, line.qty_per_unit, line.wastage_percentage,
                    line.rounding_method, line.product_uom_id,
                )
                line.write({
                    "actual_output_qty": output.actual_qty,
                    "expected_actual_packaging_qty": expected,
                })
                if line.stock_move_id:
                    lines_by_move[line.stock_move_id.id] |= line
            for move_id, lines in lines_by_move.items():
                move = self.env["stock.move"].browse(move_id)
                total_expected = sum(lines.mapped("expected_actual_packaging_qty"))
                for line in lines:
                    allocated = (
                        move.quantity * line.expected_actual_packaging_qty / total_expected
                        if total_expected else 0.0
                    )
                    line.actual_consumed_qty = allocated

    def _rebuild_packaging_moves(self):
        Move = self.env["stock.move"]
        for production in self:
            old_moves = production.move_raw_ids.filtered(
                lambda move: move.component_source == "packaging_recipe" and move.state == "draft"
            )
            old_moves.unlink()
            grouped = defaultdict(lambda: {"qty": 0.0, "lines": self.env["mrp.production.packaging.line"]})
            for line in production.packaging_line_ids:
                key = (
                    line.packaging_product_id.id, line.product_uom_id.id, line.operation_id.id,
                    production.location_src_id.id, production.company_id.id,
                )
                grouped[key]["qty"] += line.planned_packaging_qty
                grouped[key]["lines"] |= line
            for (product_id, uom_id, operation_id, _location_id, _company_id), values in grouped.items():
                product = self.env["product.product"].browse(product_id)
                uom = self.env["uom.uom"].browse(uom_id)
                move_values = production._get_move_raw_values(
                    product, values["qty"], uom, operation_id=operation_id, bom_line=False
                )
                move_values.update({
                    "component_source": "packaging_recipe",
                    "expected_packaging_qty": values["qty"],
                })
                move = Move.create(move_values)
                values["lines"].write({"stock_move_id": move.id})

    def _rebuild_finished_output_moves(self):
        """Create the stock moves that will receive every custom finished output."""
        Move = self.env["stock.move"]
        for production in self.filtered(
            lambda mo: mo.manufacturing_workflow == "custom_multi_output"
            and mo.custom_process_type == "integrated_production_packaging"
        ):
            production._sync_primary_bulk_output_line()
            output_lines = production.output_line_ids.filtered(
                lambda line: line.output_classification in ("primary_packaged", "primary_bulk")
            )
            bulk_line = output_lines.filtered(
                lambda line: line.output_classification == "primary_bulk"
            )[:1]
            main_move = production.move_finished_ids.filtered(
                lambda move: move.product_id == production.product_id
                and not move.byproduct_id
                and move.state == "draft"
            )[:1]

            for output in output_lines:
                move = output.stock_move_id.filtered(lambda item: item.state == "draft")
                if output == bulk_line and main_move:
                    move = main_move
                values = production._get_move_finished_values(
                    output.product_id.id,
                    output.planned_qty,
                    output.product_uom_id.id,
                )
                if move:
                    move.write(values)
                else:
                    move = Move.create(values)
                output.with_context(skip_multi_output_sync=True).write({"stock_move_id": move.id})

    def _sync_finished_output_move_quantities(self):
        """Apply recorded actual quantities to their linked finished stock moves."""
        for production in self.filtered(
            lambda mo: mo.manufacturing_workflow == "custom_multi_output"
            and mo.custom_process_type == "integrated_production_packaging"
        ):
            production._sync_primary_bulk_output_line()
            for output in production.output_line_ids.filtered(
                lambda line: line.output_classification in ("primary_packaged", "primary_bulk")
            ):
                if not output.stock_move_id:
                    raise UserError(_("Finished stock move is missing for %s.", output.product_id.display_name))
                output.stock_move_id.write({
                    "product_uom_qty": output.planned_qty,
                    "quantity": output.actual_qty,
                })

    def _prepare_packaging(self):
        """Build recipe snapshots, calculations, and moves in one operation.

        Operators do not need to run this manually: ``action_confirm`` calls it
        automatically.  The legacy public actions below remain available for
        integrations and draft troubleshooting.
        """
        for production in self:
            if production.state != "draft":
                raise UserError("Packaging can only be prepared on a Draft Manufacturing Order.")
            production._sync_primary_bulk_output_line()
            production._validate_custom_output_plan()
            production._snapshot_packaging_recipes()
            production._rebuild_packaging_calculations()
            production._rebuild_packaging_moves()
        return True

    def action_reload_packaging_recipes(self):
        return self._prepare_packaging()

    def action_recalculate_multi_output(self):
        return self._prepare_packaging()

    def action_confirm(self):
        custom = self.filtered(lambda mo: mo.manufacturing_workflow == "custom_multi_output")
        custom._ensure_default_packaged_output()
        custom._prepare_packaging()
        custom._rebuild_finished_output_moves()
        return super().action_confirm()

    def pre_button_mark_done(self):
        custom = self.filtered(lambda mo: mo.manufacturing_workflow == "custom_multi_output")
        custom._sync_finished_output_move_quantities()
        custom._refresh_actual_packaging_calculations()
        custom._validate_custom_output_plan(completion=True)
        return super().pre_button_mark_done()

    def _post_inventory(self, cancel_backorder=False):
        """Post the remaining bulk as the main finished quantity.

        Core Odoo always writes ``qty_producing`` onto the main finished move.
        For an integrated order the main move represents only the bulk that was
        not converted into packaged variants, so expose that amount while the
        stock moves are posted and retain it as Odoo's produced bulk quantity.
        """
        custom = self.filtered(
            lambda mo: mo.manufacturing_workflow == "custom_multi_output"
            and mo.custom_process_type == "integrated_production_packaging"
        )
        for production in custom:
            bulk_line = production.output_line_ids.filtered(
                lambda line: line.output_classification == "primary_bulk"
            )[:1]
            if bulk_line:
                production.qty_producing = bulk_line.actual_qty
        return super()._post_inventory(cancel_backorder=cancel_backorder)
