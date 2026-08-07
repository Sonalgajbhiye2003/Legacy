from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # These two source BOMs have internally consistent output/component
    # quantities and complete positive packaging recipes. Review BOMs remain
    # archived; the separate Soya Oil processing shell also remains archived.
    env.ref("legacy_mrp_master_data.bom_tsp_case_10_x_700g").active = True
    env.ref("legacy_mrp_master_data.bom_tsp_8kg_woven_bag").active = True
