"""POS MiniCOA hooks — creates journals, payment methods and links them to POS configs."""

from odoo import api, SUPERUSER_ID


def pre_init_attach_journals(cr):
    """No-op pre-init hook."""
    print("[pos_minicoa] Pre-init skipped: no environment created.")
    return True


def _get_or_create_payment_methods(env, company):
    """Ensure all FRCS-required payment methods exist and return them."""
    from odoo.addons.pos_minicoa.models.journal_setup import PAYMENT_METHODS

    PaymentMethod = env['pos.payment.method']
    Journal = env['account.journal']
    Account = env['account.account']

    # Find liquidity account
    acc_domain = [('account_type', '=', 'asset_cash')]
    if 'company_id' in Account._fields:
        acc_domain.append(('company_id', '=', company.id))
    liquidity = Account.search(acc_domain, limit=1)

    created_methods = env['pos.payment.method']

    for pm_data in PAYMENT_METHODS:
        # Get or create journal
        j_domain = [('code', '=', pm_data['journal_code'])]
        if 'company_id' in Journal._fields:
            j_domain.append(('company_id', '=', company.id))
        journal = Journal.search(j_domain, limit=1)

        if not journal:
            journal_vals = {
                'name': pm_data['journal_name'],
                'code': pm_data['journal_code'],
                'type': pm_data['journal_type'],
                'show_on_dashboard': True,
            }
            if 'company_id' in Journal._fields:
                journal_vals['company_id'] = company.id
            if liquidity:
                journal_vals['default_account_id'] = liquidity.id
            journal = Journal.create(journal_vals)
            print(f"[pos_minicoa] Created journal: {pm_data['journal_name']}")

        # Get or create payment method
        pm_domain = [('name', '=', pm_data['name'])]
        if 'company_id' in PaymentMethod._fields:
            pm_domain.append(('company_id', '=', company.id))
        payment_method = PaymentMethod.with_context(active_test=False).search(pm_domain, limit=1)

        if not payment_method:
            pm_vals = {
                'name': pm_data['name'],
                'journal_id': journal.id,
                'is_cash_count': pm_data['is_cash_count'],
            }
            if 'company_id' in PaymentMethod._fields:
                pm_vals['company_id'] = company.id
            payment_method = PaymentMethod.create(pm_vals)
            print(f"[pos_minicoa] Created payment method: {pm_data['name']}")

        created_methods |= payment_method

    return created_methods


def _link_methods_to_all_configs(env, company, methods):
    """Link payment methods to all POS configs for this company."""
    Config = env['pos.config']
    cfg_domain = []
    if 'company_id' in Config._fields:
        cfg_domain.append(('company_id', '=', company.id))
    configs = Config.search(cfg_domain)
    for cfg in configs:
        cmds = []
        for pm in methods:
            if pm not in cfg.payment_method_ids:
                cmds.append((4, pm.id))
        if cmds:
            cfg.write({'payment_method_ids': cmds})
            print(f"[pos_minicoa] Linked {len(cmds)} method(s) to POS config: {cfg.name}")


def post_init_setup(env_or_cr, registry=None):
    """Executed after installation: create journals, payment methods and link to POS."""
    cr = getattr(env_or_cr, 'cr', env_or_cr)
    env = api.Environment(cr, SUPERUSER_ID, {})
    companies = env['res.company'].search([])
    print(f"[pos_minicoa] Post-init: setting up Fiji POS for {len(companies)} company(ies)")

    for company in companies:
        if company.country_id.code != 'FJ':
            print(f"[pos_minicoa] Skipping {company.name} (not Fiji)")
            continue

        print(f"[pos_minicoa] Processing company: {company.name}")
        with env.cr.savepoint():
            try:
                methods = _get_or_create_payment_methods(env, company)
                _link_methods_to_all_configs(env, company, methods)
                print(f"[pos_minicoa] {company.name}: setup complete.")
            except Exception as e:
                print(f"[pos_minicoa] {company.name}: error during setup -> {e}")

    return True
