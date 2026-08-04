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
