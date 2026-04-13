from odoo import api, SUPERUSER_ID

def post_init_hook(env):
    _create_default_products(env)
    _setup_stock_accounts(env)


def _create_default_products(env):
    """Create default products required by FreePOS on fresh install."""
    Product = env['product.template'].sudo()

    # Deposit product for Advance Sale prepayments
    existing = Product.search([('name', '=', 'Deposit')], limit=1)
    if not existing:
        Product.create({
            'name': 'Deposit',
            'type': 'service',
            'available_in_pos': True,
            'list_price': 0.0,
            'sale_ok': True,
            'purchase_ok': False,
            'description_sale': 'Advance deposit / prepayment for goods or services not yet delivered',
        })
        import logging
        logging.getLogger(__name__).info("FreePOS: Created default Deposit product")


def _setup_stock_accounts(env):
    Account = env['account.account']
    Imd = env['ir.model.data'].sudo()

    stocks = {
        'stock_in': '12100',
        'stock_out': '12101',
        'stock_valuation': '12000',
    }

    for company in env['res.company'].search([]):
        for technical_name, code in stocks.items():
            account = Account.search([
                ('code', '=', code),
                ('company_ids', 'in', company.id),
            ], limit=1)
            if not account:
                continue
            existing = Imd.search([
                ('module', '=', 'l10n_fj_minicoa'),
                ('name', '=', technical_name),
            ], limit=1)
            if existing:
                if existing.res_id != account.id:
                    existing.write({'model': 'account.account', 'res_id': account.id})
            else:
                Imd.create({
                    'module': 'l10n_fj_minicoa',
                    'name': technical_name,
                    'model': 'account.account',
                    'res_id': account.id,
                    'noupdate': False,
                })
