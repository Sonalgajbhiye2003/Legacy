"""Add the production-material presentation without touching ledger/config data."""


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    report = env.ref('legacy_financial_reports.legacy_pl', raise_if_not_found=False)
    credit_heading = env.ref('legacy_financial_reports.legacy_pl_row_88', raise_if_not_found=False)
    if not report:
        return
    if credit_heading and credit_heading.sequence < 92:
        credit_heading.write({'sequence': 92})
    if not report.legacy_raw_material_category_ids and not report.legacy_packaging_category_ids:
        raw = env.ref('legacy_mrp_master_data.cat_raw_materials', raise_if_not_found=False)
        packaging = env.ref('legacy_mrp_master_data.cat_packaging_materials', raise_if_not_found=False)
        if raw and packaging:
            report.write({
                'legacy_raw_material_category_ids': [(6, 0, raw.ids)],
                'legacy_packaging_category_ids': [(6, 0, packaging.ids)],
            })
