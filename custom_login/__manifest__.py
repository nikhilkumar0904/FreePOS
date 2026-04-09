{
    'name': 'Custom Login',
    'version': '1.0',
    'category': 'Website',
    'summary': 'Custom login page with role selection',
    'description': 'Replaces default Odoo login page with role selection',
    'depends': ['web', 'auth_signup', 'point_of_sale'],
    'data': [
        "views/login_template.xml",
        "views/res_config_settings_views.xml",
        "security/custom_login_groups.xml",
        "security/ir.model.access.csv",
        "data/test_users.xml",
    ],
    'assets': {
        "web.assets_frontend":[
            ('include', 'web._assets_bootstrap_frontend'),
            "custom_login/static/src/css/login.scss",
        ],

    },
    'installable': True,
    'application': False,
}

