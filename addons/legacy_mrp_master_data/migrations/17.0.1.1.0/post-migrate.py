from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env.ref("legacy_mrp_master_data.prod_bulk_tsp").name = "Bulk Soya Chunks (TSP)"
    env.ref("legacy_mrp_master_data.prod_crude_oil").name = "Soya Oil (Crude)"

    for xmlid in (
        "bom_tsp_case_20_x_90g",
        "bom_tsp_case_10_x_700g",
        "bom_tsp_case_5_x_700g",
        "bom_tsp_3kg_bag",
        "bom_tsp_3kg_woven_bag",
        "bom_tsp_8kg_woven_bag",
    ):
        env.ref(f"legacy_mrp_master_data.{xmlid}").active = False
