from odoo import fields, models, tools

from .common import WORK_TYPE_SELECTION


class LegacyRepairCostReconciliation(models.Model):
    _name = "legacy.repair.cost.reconciliation"
    _description = "Repair/Build Cost Reconciliation"
    _auto = False
    _rec_name = "repair_order_id"
    _order = "id desc"

    repair_order_id = fields.Many2one("repair.order", readonly=True)
    maintenance_request_id = fields.Many2one("maintenance.request", readonly=True)
    order_type = fields.Selection(WORK_TYPE_SELECTION, readonly=True)
    order_state = fields.Char(readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    equipment_id = fields.Many2one("maintenance.equipment", readonly=True)
    workcenter_id = fields.Many2one("mrp.workcenter", readonly=True)
    material_cost = fields.Monetary(currency_field="currency_id", readonly=True)
    stock_valuation_value = fields.Monetary(currency_field="currency_id", readonly=True)
    material_journal_value = fields.Monetary(currency_field="currency_id", readonly=True)
    material_difference = fields.Monetary(currency_field="currency_id", readonly=True)
    approved_labour_cost = fields.Monetary(currency_field="currency_id", readonly=True)
    labour_journal_value = fields.Monetary(currency_field="currency_id", readonly=True)
    labour_difference = fields.Monetary(currency_field="currency_id", readonly=True)
    posted_capex = fields.Monetary(currency_field="currency_id", readonly=True)
    cwip_value = fields.Monetary(currency_field="currency_id", readonly=True)
    capitalization_value = fields.Monetary(currency_field="currency_id", readonly=True)
    capex_difference = fields.Monetary(currency_field="currency_id", readonly=True)
    reconciliation_state = fields.Selection([("ok", "Reconciled"), ("exception", "Exception")], readonly=True)
    exception_summary = fields.Char(readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW legacy_repair_cost_reconciliation AS (
                WITH amounts AS (
                    SELECT ro.id,
                           ro.id AS repair_order_id,
                           ro.legacy_maintenance_request_id AS maintenance_request_id,
                           ro.legacy_order_type AS order_type,
                           ro.state AS order_state,
                           ro.company_id,
                           c.currency_id,
                           ro.legacy_equipment_id AS equipment_id,
                           COALESCE(ro.legacy_workcenter_id, ro.legacy_target_workcenter_id) AS workcenter_id,
                           COALESCE((SELECT ABS(SUM(svl.value)) FROM stock_request sr JOIN stock_valuation_layer svl ON svl.stock_move_id = sr.legacy_repair_move_id WHERE sr.legacy_repair_order_id = ro.id), 0) AS material_cost,
                           COALESCE((SELECT ABS(SUM(svl.value)) FROM stock_request sr JOIN stock_valuation_layer svl ON svl.stock_move_id = sr.legacy_repair_move_id WHERE sr.legacy_repair_order_id = ro.id), 0) AS stock_valuation_value,
                           COALESCE((SELECT SUM(aml.debit) FROM account_move_line aml WHERE aml.move_id IN (
                               SELECT sr.legacy_journal_entry_id FROM stock_request sr WHERE sr.legacy_repair_order_id = ro.id AND sr.legacy_journal_entry_id IS NOT NULL
                               UNION SELECT svl.account_move_id FROM stock_request sr JOIN stock_valuation_layer svl ON svl.stock_move_id = sr.legacy_repair_move_id WHERE sr.legacy_repair_order_id = ro.id AND svl.account_move_id IS NOT NULL
                           )), 0) AS material_journal_value,
                           COALESCE((SELECT SUM(l.labour_cost) FROM legacy_repair_labour l WHERE l.repair_order_id = ro.id AND l.approval_state = 'approved'), 0) AS approved_labour_cost,
                           COALESCE((SELECT SUM(aml.debit) FROM account_move_line aml JOIN legacy_repair_labour l ON l.id = aml.legacy_labour_id WHERE l.repair_order_id = ro.id AND aml.parent_state = 'posted'), 0) AS labour_journal_value,
                           COALESCE(ro.legacy_total_capex, 0) AS posted_capex,
                           COALESCE((SELECT SUM(aml.balance) FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id WHERE am.legacy_repair_order_id = ro.id AND am.state = 'posted' AND am.legacy_posting_type IN ('material', 'material_return', 'labour') AND aml.account_id = c.legacy_cwip_account_id), 0) AS cwip_value,
                           COALESCE((SELECT SUM(aml.debit) FROM account_move_line aml WHERE aml.move_id = ro.legacy_capitalization_move_id AND aml.account_id = c.legacy_ppe_account_id AND aml.parent_state = 'posted'), 0) AS capitalization_value,
                           EXISTS(SELECT 1 FROM stock_request sr WHERE sr.legacy_repair_order_id = ro.id AND sr.legacy_finance_approval_state != 'approved') AS missing_material_approval,
                           EXISTS(SELECT 1 FROM stock_request sr WHERE sr.legacy_repair_order_id = ro.id AND sr.legacy_accounting_status = 'not_posted' AND sr.legacy_repair_move_id IS NOT NULL) AS unposted_material,
                           EXISTS(SELECT 1 FROM legacy_repair_labour l WHERE l.repair_order_id = ro.id AND (l.approval_state != 'approved' OR l.accounting_status = 'not_posted')) AS unposted_labour
                    FROM repair_order ro JOIN res_company c ON c.id = ro.company_id
                )
                SELECT a.*,
                       a.material_cost - a.material_journal_value AS material_difference,
                       a.approved_labour_cost - a.labour_journal_value AS labour_difference,
                       a.posted_capex - a.cwip_value AS capex_difference,
                       CASE WHEN ABS(a.material_cost - a.material_journal_value) > 0.01 OR ABS(a.approved_labour_cost - a.labour_journal_value) > 0.01 OR (a.order_type = 'build' AND ABS(a.posted_capex - a.cwip_value) > 0.01) OR a.missing_material_approval OR a.unposted_material OR a.unposted_labour OR (a.order_type = 'build' AND a.order_state = 'done' AND a.capitalization_value = 0) THEN 'exception' ELSE 'ok' END AS reconciliation_state,
                       CONCAT_WS('; ',
                           CASE WHEN a.missing_material_approval THEN 'Missing CAPEX/OPEX approval' END,
                           CASE WHEN a.unposted_material THEN 'Unposted material' END,
                           CASE WHEN a.unposted_labour THEN 'Unposted or unapproved labour' END,
                           CASE WHEN ABS(a.material_cost - a.material_journal_value) > 0.01 THEN 'Material/valuation/journal mismatch' END,
                           CASE WHEN ABS(a.approved_labour_cost - a.labour_journal_value) > 0.01 THEN 'Labour posting mismatch' END,
                           CASE WHEN a.order_type = 'build' AND ABS(a.posted_capex - a.cwip_value) > 0.01 THEN 'CWIP mismatch' END,
                           CASE WHEN a.order_type = 'build' AND a.order_state = 'done' AND a.capitalization_value = 0 THEN 'Completed Build not capitalized' END
                       ) AS exception_summary
                FROM amounts a
            )
            """
        )
