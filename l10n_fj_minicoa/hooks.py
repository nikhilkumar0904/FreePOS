from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

# -------------------------
# 1) PRE-INIT (optional)
# -------------------------
def pre_init_hook(cr_or_env):
    """Run before XML data loads — clean up duplicate Fiji taxes early."""
    # Handle both cases: env or cursor (for compatibility)
    cr = getattr(cr_or_env, 'cr', cr_or_env)
    env = api.Environment(cr, SUPERUSER_ID, {})
    Tax = env['account.tax']
    Company = env['res.company']

    # Archive duplicate active VAT rates for Fiji
    # Find all unique rates and deduplicate per rate/type
    all_rates = Tax.search([
        ('country_id.code', '=', 'FJ'),
        ('amount_type', '=', 'percent'),
        ('type_tax_use', 'in', ['sale', 'purchase']),
        ('active', '=', True),
    ]).mapped('amount')
    for rate in set(all_rates):
        dups = Tax.search([
            ('country_id.code', '=', 'FJ'),
            ('amount_type', '=', 'percent'),
            ('amount', '=', rate),
            ('type_tax_use', 'in', ['sale', 'purchase']),
            ('active', '=', True),
        ], order='id asc')
        if len(dups) > 2:
            dups[2:].write({'active': False})
            _logger.info("   archived %s extra VAT %.1f%% taxes", len(dups) - 2, rate)


# -------------------------
# 2) POST-INIT
# -------------------------
def post_init_setup(env_or_cr, registry=None):
    """Fiji post-install setup — runs after module install or update."""
    cr = getattr(env_or_cr, "cr", env_or_cr)
    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info("Fiji post-install setup started")


    Company = env['res.company']
    Tax = env['account.tax']
    TaxGroup = env['account.tax.group']
    Account = env['account.account']
    # Label map is now fetched from TaxCore via sync_tax_rates_from_taxcore()
    # This is only a fallback used if TaxCore is unavailable during install
    fallback_label_map = {
        0.0: 'G',
        12.5: 'A',
    }

    # Helper: ensure one FRCS VAT tax group PER COMPANY
    def ensure_tax_group(company):
        grp = TaxGroup.search([('name', '=', 'FRCS VAT'), ('company_id', '=', company.id)], limit=1)
        if not grp:
            grp = TaxGroup.create({
                'name': 'FRCS VAT',
                'company_id': company.id,
                'country_id': env.ref('base.fj').id if env.ref('base.fj', raise_if_not_found=False) else False,
                'sequence': 10,
            })
            _logger.info("  created tax group FRCS VAT for %s (id=%s)", company.name, grp.id)
        return grp

    # Helper: ensure repartition lines are exactly one base (100) + one tax (100)
    def normalize_repartition_lines(tax):
        # Purge all lines and rebuild predictable structure in one go so the
        # mandatory base line is always present while passing ORM constraints.
        tax.write({
            'invoice_repartition_line_ids': [
                (5, 0, 0),
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0, 'account_id': None}),
            ],
            'refund_repartition_line_ids': [
                (5, 0, 0),
                (0, 0, {'repartition_type': 'base', 'factor_percent': 100.0}),
                (0, 0, {'repartition_type': 'tax', 'factor_percent': 100.0, 'account_id': None}),
            ],
        })

    # Helper: assign tax accounts on tax lines (not on base lines)
    def set_tax_accounts(tax, collected_acc, paid_acc):
        tax_lines = (tax.invoice_repartition_line_ids | tax.refund_repartition_line_ids).filtered(
            lambda l: l.repartition_type == 'tax'
        )
        acc = collected_acc if tax.type_tax_use == 'sale' else paid_acc
        if acc:
            tax_lines.write({'account_id': acc.id})

    # (Optional) apply country/currency to companies
    fj_country = env.ref('base.fj', raise_if_not_found=False)
    fjd = env['res.currency'].search([('name', '=', 'FJD')], limit=1)

    for company in Company.search([]):
        _logger.info("Configuring %s", company.name)
        update_vals = {}
        if fj_country and not company.country_id:
            update_vals['country_id'] = fj_country.id
        if fjd and company.currency_id != fjd:
            update_vals['currency_id'] = fjd.id
        # account_fiscal_country_id is what Odoo uses for tax validation
        # Must match the tax country or billing/invoicing will fail
        if fj_country and company.account_fiscal_country_id != fj_country:
            update_vals['account_fiscal_country_id'] = fj_country.id
        if update_vals:
            company.write(update_vals)
            _logger.info("  updated company %s: %s", company.name, list(update_vals.keys()))

        group = ensure_tax_group(company)

        domain_collected = [('code', '=', '21310')]
        domain_paid = [('code', '=', '21330')]

        if 'company_id' in Account._fields:
            domain_collected.append(('company_id', '=', company.id))
            domain_paid.append(('company_id', '=', company.id))

        acc_collected = Account.search(domain_collected, limit=1)
        acc_paid = Account.search(domain_paid, limit=1)
        # Normalize all existing taxes for this company
        # Rates are NOT hardcoded - they come from TaxCore via sync_tax_rates_from_taxcore()
        # We only create minimal default taxes if none exist at all
        existing_taxes = Tax.search([
            ('company_id', '=', company.id),
            ('amount_type', '=', 'percent'),
        ])

        if not existing_taxes:
            # Create minimal defaults only on fresh install with no taxes
            for rate, use in [(0.0, 'sale'), (0.0, 'purchase'), (12.5, 'sale'), (12.5, 'purchase')]:
                Tax.create({
                    'name': f"VAT {rate}% ({'Sales' if use == 'sale' else 'Purchase'})",
                    'type_tax_use': use,
                    'amount_type': 'percent',
                    'amount': rate,
                    'company_id': company.id,
                    'tax_group_id': group.id,
                    'active': True,
                    'price_include': True,
                    'invoice_label': fallback_label_map.get(rate, 'G'),
                })
                _logger.info("  created minimal default %s %.1f%% tax", use, rate)
            existing_taxes = Tax.search([('company_id', '=', company.id), ('amount_type', '=', 'percent')])

        # Normalize all taxes - fix repartition lines, accounts, price_include
        for keep in existing_taxes:
            if not keep.price_include:
                keep.price_include = True
            normalize_repartition_lines(keep)
            set_tax_accounts(keep, acc_collected, acc_paid)
            # Apply fallback label only if no label set
            if not keep.invoice_label:
                label = fallback_label_map.get(keep.amount)
                if label:
                    keep.invoice_label = label
        # Company defaults - use highest rate sale tax and lowest rate purchase tax
        sale_taxes = Tax.search([
            ('company_id', '=', company.id),
            ('type_tax_use', '=', 'sale'),
            ('amount_type', '=', 'percent'),
            ('active', '=', True),
        ], order='amount desc')
        purch_taxes = Tax.search([
            ('company_id', '=', company.id),
            ('type_tax_use', '=', 'purchase'),
            ('amount_type', '=', 'percent'),
            ('active', '=', True),
        ], order='amount asc')
        vals = {}
        if sale_taxes:
            vals['account_sale_tax_id'] = sale_taxes[0].id
        if purch_taxes:
            vals['account_purchase_tax_id'] = purch_taxes[0].id
        if vals:
            company.write(vals)

        # Set tax-inclusive pricing as default for Fiji (prices include VAT)
        IrConfig = env['ir.config_parameter'].sudo()
        IrConfig.set_param('account.show_line_subtotals_tax_selection', 'tax_included')

    # Fix account 213300 VAT Paid — must be asset_current not asset_receivable
    # Using asset_receivable causes "account used in purchase operation" error on billing
    vat_paid = env['account.account'].search([('code', '=', '21330')], limit=1)
    if vat_paid and vat_paid.account_type == 'asset_receivable':
        vat_paid.write({'account_type': 'asset_current', 'reconcile': False})
        _logger.info("Fixed account 21330 VAT Paid: asset_receivable -> asset_current")

    # Fix fiscal country — must be set or tax validation fails on invoices/bills
    fj = env.ref('base.fj', raise_if_not_found=False)
    for company in Company.search([]):
        if fj and company.account_fiscal_country_id != fj:
            company.write({'account_fiscal_country_id': fj.id})
            _logger.info("Fixed fiscal country to Fiji for %s", company.name)

    # Set POS receivable account (required for session closing)
    for company in Company.search([]):
        if not company.account_default_pos_receivable_account_id:
            receivable = env['account.account'].search([
                ('code', '=', '11200'),
                ('account_type', '=', 'asset_receivable'),
            ], limit=1)
            if receivable:
                company.write({'account_default_pos_receivable_account_id': receivable.id})
                _logger.info("Set POS receivable account to %s for %s", receivable.name, company.name)

        # Clean up duplicate 11200 accounts
        duplicates = env['account.account'].search([
            ('code', '=', '11200'),
            ('account_type', '=', 'asset_receivable'),
        ], order='id asc')
        if len(duplicates) > 1:
            duplicates[1:].write({'active': False})
            _logger.info("Archived %s duplicate Trade Debtors accounts", len(duplicates) - 1)

    # Attempt to sync tax rates from TaxCore
    # Requires V-SDC config to be already set up - will silently skip if not
    try:
        config = env['frcs.vsdc.config'].search([], limit=1)
        if config and config.vsdc_url:
            result = env['taxcore.client'].sync_tax_rates_from_taxcore()
            if result.get('success'):
                _logger.info("Post-install TaxCore tax sync complete: %s", result.get('synced'))
            else:
                _logger.info("Post-install TaxCore sync skipped: %s", result.get('error'))
        else:
            _logger.info("Post-install TaxCore sync skipped: no V-SDC config yet")
    except Exception as e:
        _logger.info("Post-install TaxCore sync not available: %s", e)

    _logger.info("Fiji post-install setup complete.")
