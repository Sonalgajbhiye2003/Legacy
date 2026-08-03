from . import models


def post_init_hook(env):
    process_moves = env["stock.move"].search([
        ("raw_material_production_id", "!=", False),
        ("bom_line_id", "!=", False),
        ("component_source", "!=", "process_bom"),
    ])
    process_moves.write({"component_source": "process_bom"})
