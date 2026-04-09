from odoo import api, SUPERUSER_ID

def post_init_hook(env):
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
