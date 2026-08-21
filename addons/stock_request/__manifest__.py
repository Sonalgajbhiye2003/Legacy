# Copyright 2017-2021 ForgeFlow, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

{
    "name": "Material Requisition",
    "summary": "Material requisitions with configurable approval matrix",
    "version": "17.0.4.0.1",
    "license": "LGPL-3",
    "website": "https://github.com/OCA/stock-logistics-request",
    "author": "ForgeFlow, Odoo Community Association (OCA)",
    "maintainers": ["LoisRForgeFlow", "etobella"],
    "category": "Warehouse Management",
    "depends": ["stock", "purchase_stock", "mrp", "analytic"],
    "data": [
        "security/stock_request_security.xml",
        "security/ir.model.access.csv",
        "wizard/stock_request_rejection_wizard_views.xml",
        "wizard/stock_request_fulfillment_wizard_views.xml",
        "views/product.xml",
        "views/stock_request_views.xml",
        "views/stock_request_allocation_views.xml",
        "views/stock_move_views.xml",
        "views/stock_picking_views.xml",
        "views/stock_request_order_views.xml",
        "views/res_config_settings_views.xml",
        "views/stock_request_menu.xml",
        "views/stock_request_approval_config_views.xml",
        "data/stock_request_sequence_data.xml",
    ],
    "installable": True,
}
