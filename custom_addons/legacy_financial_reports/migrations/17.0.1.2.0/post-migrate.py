"""Keep the new noupdate expression records aligned with their distinct engines."""


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    formulas = {
        'legacy_pl_row_90_period': '_report_custom_engine_legacy_raw_material_consumed',
        'legacy_pl_row_90_ytd': '_report_custom_engine_legacy_raw_material_consumed',
        'legacy_pl_row_91_period': '_report_custom_engine_legacy_packaging_consumed',
        'legacy_pl_row_91_ytd': '_report_custom_engine_legacy_packaging_consumed',
        'legacy_pl_row_92_period': '_report_custom_engine_legacy_production_material_total',
        'legacy_pl_row_92_ytd': '_report_custom_engine_legacy_production_material_total',
    }
    for xmlid, formula in formulas.items():
        expression = env.ref(f'legacy_financial_reports.{xmlid}', raise_if_not_found=False)
        if expression and (expression.engine != 'custom' or expression.formula != formula):
            expression.write({'engine': 'custom', 'formula': formula})
