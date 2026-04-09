{
    'name': 'Custom POS',
    'version': '18.0.1.0.2',
    'summary': 'Base POS with customization for MSMEs',
    'description': 'Replaces default Odoo login page with role selection',
    'depends': ['point_of_sale'],
    'data': [
        "security/ir.model.access.csv",
        "views/frcs_reports.xml",
        "views/frcs_vsdc_config_views.xml",
        "views/pos_config_views.xml",
        "data/ir_cron.xml",
    ],
    'assets': {
        'point_of_sale.assets_prod': [
            "custom_pos/static/src/css/pos_ui.css",
            "custom_pos/static/src/js/frcs_payment.js",
            "custom_pos/static/src/js/frcs_refund.js",
            "custom_pos/static/src/js/frcs_ticketscreen.js",
            "custom_pos/static/src/js/frcs_navbar.js",
            "custom_pos/static/src/js/frcs_order.js",
            "custom_pos/static/src/xml/frcs_taxcore.xml",
            "custom_pos/static/src/xml/frcs_ticketscreen.xml",
            "custom_pos/static/src/xml/frcs_receiptscreen.xml",
            "custom_pos/static/src/xml/frcs_actionpad.xml",
            "custom_pos/static/src/xml/frcs_navbar.xml",
            
        ],
        'point_of_sale.assets': [
            "custom_pos/static/src/js/frcs_payment.js",
            "custom_pos/static/src/js/frcs_refund.js",
            "custom_pos/static/src/js/frcs_ticketscreen.js",
            "custom_pos/static/src/js/frcs_navbar.js",
            "custom_pos/static/src/js/frcs_order.js",
            "custom_pos/static/src/xml/frcs_taxcore.xml",
            "custom_pos/static/src/xml/frcs_ticketscreen.xml",
            "custom_pos/static/src/xml/frcs_receiptscreen.xml",
            "custom_pos/static/src/xml/frcs_actionpad.xml",
            "custom_pos/static/src/xml/frcs_navbar.xml",
        ],
        'point_of_sale.assets_qweb': [
            "custom_pos/static/src/xml/frcs_taxcore.xml",
            "custom_pos/static/src/xml/frcs_ticketscreen.xml",
            "custom_pos/static/src/xml/frcs_receiptscreen.xml",
            "custom_pos/static/src/xml/frcs_actionpad.xml",
            "custom_pos/static/src/xml/frcs_navbar.xml",
        ],
        'web.assets_backend': [
            "custom_pos/static/src/js/frcs_fiscal_report.js",
            "custom_pos/static/src/xml/frcs_fiscal_report.xml",
        ],

    },
    'installable': True,
    'application': True
}
