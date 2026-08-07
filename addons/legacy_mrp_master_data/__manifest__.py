{
    "name": "Legacy MRP Master Data",
    "summary": "Legacy Manufacturing product, warehouse, work-center, BoM, operation, and packaging master data",
    "version": "17.0.1.1.0",
    "category": "Manufacturing/Manufacturing",
    "license": "LGPL-3",
    "author": "Legacy Manufacturers",
    "depends": [
        "mrp_multi_output_packaging",
        "purchase_stock",
        "mrp_workorder"
    ],
    "data": [
        "data/product_categories.xml",
        "data/products.xml",
        "data/variant_products.xml",
        "data/warehouse_locations.xml",
        "data/warehouse_routes.xml",
        "data/workcenters.xml",
        "data/boms.xml",
        "data/operations.xml",
        "data/bom_lines.xml",
        "data/byproducts.xml",
        "data/packaging_recipes.xml"
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False
}
