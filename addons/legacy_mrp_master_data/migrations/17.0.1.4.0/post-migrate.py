from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    legacy_pack_boms = (
        "bom_instant_thobwa_case_50_x_50g",
        "bom_instant_thobwa_25kg_bag",
        "bom_tsp_case_20_x_90g",
        "bom_tsp_case_10_x_700g",
        "bom_tsp_case_5_x_700g",
        "bom_tsp_3kg_bag",
        "bom_tsp_3kg_woven_bag",
        "bom_tsp_8kg_woven_bag",
        "bom_puffs_case_50_x_16g",
        "bom_zed_crunch_puffs_case_6_x_22",
        "bom_puffs_case_30_x_60g",
    )
    for xmlid in legacy_pack_boms:
        env.ref(f"legacy_mrp_master_data.{xmlid}").active = False

    process_boms = (
        "bom_soya_chunks_single_process",
        "bom_instant_thobwa_single_process",
        "bom_corn_puffs_single_process",
    )
    for xmlid in process_boms:
        env.ref(f"legacy_mrp_master_data.{xmlid}").write({
            "active": True,
            "manufacturing_workflow": "custom_multi_output",
            "custom_process_type": "integrated_production_packaging",
            "default_packaged_product_id": False,
        })

    template_operations = {
        "tmpl_fg_tsp": "op_soya_chunks_100_packaging",
        "tmpl_fg_instant_thobwa": "op_thobwa_single_packaging",
        "tmpl_fg_corn_puffs": "op_puffs_single_packaging",
    }
    for template_xmlid, operation_xmlid in template_operations.items():
        template = env.ref(f"legacy_mrp_master_data.{template_xmlid}")
        operation = env.ref(f"legacy_mrp_master_data.{operation_xmlid}")
        variants = template.with_context(active_test=False).product_variant_ids.filtered(
            lambda product: product.active and product.packaging_enabled
        )
        for product in variants:
            product.default_packaging_operation_id = operation
            recipe = product.packaging_recipe_id
            if not recipe:
                continue
            recipe.operation_id = operation
            recipe.line_ids.write({"operation_id": operation.id})
