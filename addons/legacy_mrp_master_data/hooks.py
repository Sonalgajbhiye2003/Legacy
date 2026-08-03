from odoo import Command


QUALITY_DEFS = {'TSP': ['Soya bean receipt inspection', 'Cleaning verification', 'Weight verification', 'Extrusion temperature: 110-160C', 'Low-fat cake thickness: 3-6mm', 'Second extrusion temperature: 140-160C', 'Moisture content: below 10%', 'Packaging verification', 'Final QC release'], 'Instant Thobwa': ['Raw-material inspection', 'Sieve size: 1.5mm', 'Mixing time: 5-7 minutes', 'Date-code verification', 'Packaging-quality verification', 'Final QC release'], 'Instant Porridge': ['Maize and soya inspection', 'Extrusion temperature: 50-150C', 'Sieve size: 1.5mm', 'Final mixing time: 5-10 minutes', 'Packaging verification', 'Final QC release'], 'Corn Puffs': ['Raw-material quantity and quality verification', 'Mixing verification', 'Extrusion/cooking verification', 'Seasoning verification', 'Packaging verification', 'Final QC release']}


def _ensure_xmlid(env, xmlid, record):
    module, name = xmlid.split(".", 1)
    values = {"module": module, "name": name, "model": record._name, "res_id": record.id, "noupdate": True}
    existing = env["ir.model.data"].sudo().search([("module", "=", module), ("name", "=", name)], limit=1)
    if existing:
        existing.write(values)
    else:
        env["ir.model.data"].sudo().create(values)


def _ensure_location(env, xmlid_name, name, usage, parent):
    xmlid = "legacy_mrp_master_data." + xmlid_name
    existing = env.ref(xmlid, raise_if_not_found=False)
    if existing:
        return existing
    location = env["stock.location"].sudo().search([
        ("name", "=", name), ("location_id", "=", parent.id), ("usage", "=", usage)
    ], limit=1)
    if not location:
        location = env["stock.location"].sudo().create({
            "name": name,
            "usage": usage,
            "location_id": parent.id,
            "company_id": env.company.id,
        })
    _ensure_xmlid(env, xmlid, location)
    return location


def _xmlid_name(text):
    text = text.lower().replace(" ", "_").replace("-", "_").replace("/", "_").replace(":", "")
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in text)


def _ensure_quality_point(env, xmlid_name, name, picking_type, sequence):
    if "quality.point" not in env:
        return None
    xmlid = "legacy_mrp_master_data." + xmlid_name
    existing = env.ref(xmlid, raise_if_not_found=False)
    if existing:
        return existing
    point = env["quality.point"].sudo().search([
        ("name", "=", name), ("company_id", "=", env.company.id)
    ], limit=1)
    values = {
        "name": name,
        "company_id": env.company.id,
        "picking_type_ids": [Command.set([picking_type.id])],
        "sequence": sequence,
    }
    if not point:
        point = env["quality.point"].sudo().create(values)
    else:
        point.write(values)
    _ensure_xmlid(env, xmlid, point)
    return point


def post_init_hook(env):
    warehouse = env.ref("legacy_mrp_master_data.warehouse_legacy_main", raise_if_not_found=False)
    if not warehouse:
        return
    stock_parent = warehouse.lot_stock_id
    warehouse_parent = warehouse.view_location_id
    production_parent = _ensure_location(env, "loc_legacy_production", "Production", "view", warehouse_parent)
    _ensure_location(env, "loc_legacy_stock_raw_materials", "Raw Materials", "internal", stock_parent)
    _ensure_location(env, "loc_legacy_stock_packaging_materials", "Packaging Materials", "internal", stock_parent)
    _ensure_location(env, "loc_legacy_stock_finished_goods", "Finished Goods", "internal", stock_parent)
    _ensure_location(env, "loc_legacy_stock_spares", "Spares", "internal", stock_parent)
    _ensure_location(env, "loc_legacy_stock_by_products", "By-products", "internal", stock_parent)
    _ensure_location(env, "loc_legacy_production_wip", "Work in Progress", "internal", production_parent)

    picking_type = getattr(warehouse, "manu_type_id", False)
    if picking_type and "quality.point" in env:
        sequence = 10
        for group, points in QUALITY_DEFS.items():
            for point in points:
                _ensure_quality_point(env, "qp_" + _xmlid_name(group + "_" + point), f"{group} - {point}", picking_type, sequence)
                sequence += 10
