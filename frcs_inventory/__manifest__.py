{
    "name": "FRCS Inventory",
    "version": "1.0.1",
    "summary": "Inventory extensions for FRCS compliance (GTIN, tax label, groundwork)",
    "author": "USP Team 10",
    "license": "LGPL-3",
    "depends": ["base", "stock", "product", "account", "point_of_sale", "l10n_fj_minicoa"],  # POS + CoA + FRCS
    "data": [
        "security/ir.model.access.csv",
        "data/product_categories.xml",           # loads after tax group
        "data/default_products.xml",              # default Deposit product for Advance Sales
        "views/product_views.xml",
        "views/tax_products_views.xml",
        "views/server_actions.xml",
        "views/inventory_dashboard.xml",
        "views/remove_overview_menu.xml",
        
        "report/product_master_report.xml",
        "views/menu_actions.xml",

    ],
    "assets": {
        "web.assets_backend": [
            "frcs_inventory/static/src/css/product_qty_column.css",
            "frcs_inventory/static/src/js/inventory_dashboard.js",
            "frcs_inventory/static/src/js/hide_stock_dashboard.js",
            "frcs_inventory/static/src/xml/inventory_dashboard.xml",
        ],
        "point_of_sale.assets": [
            # Keep POS UI minimal and compatible; custom PaymentScreen patch removed for now.
            "frcs_inventory/static/src/js/pos_total_price.js",
            "frcs_inventory/static/src/xml/pos_total_receipt.xml",
            "frcs_inventory/static/src/js/pos_debug_hook.js",
        ],
    },
    "installable": True,
    "application": False,

    'post_init_hook': 'post_init_hook',

}
