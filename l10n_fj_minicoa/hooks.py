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

    # Archive duplicate active VAT rates for Fiji if there are more than 2 per rate/type
    for rate in (0.0, 9.0, 12.5, 15.0):
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
    label_map = {
        0.0: 'G',
        9.0: 'B',
        12.5: 'A',
        15.0: 'A',
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
        if fj_country and not company.country_id:
            company.write({'country_id': fj_country.id})
        if fjd and company.currency_id != fjd:
            company.write({'currency_id': fjd.id})

        group = ensure_tax_group(company)

        domain_collected = [('code', '=', '21310')]
        domain_paid = [('code', '=', '21330')]

        if 'company_id' in Account._fields:
            domain_collected.append(('company_id', '=', company.id))
            domain_paid.append(('company_id', '=', company.id))

        acc_collected = Account.search(domain_collected, limit=1)
        acc_paid = Account.search(domain_paid, limit=1)
        # Ensure each (rate, use) exists once; normalize repartition; set accounts
        for rate in (0.0, 9.0, 12.5, 15.0):
            for use in ('sale', 'purchase'):
                taxes = Tax.search([
                    ('company_id', '=', company.id),
                    ('type_tax_use', '=', use),
                    ('amount_type', '=', 'percent'),
                    ('amount', '=', rate),
                ], order='id asc')

                if taxes:
                    # Keep the first, archive extras
                    keep = taxes[0]
                    extras = taxes[1:]
                    if extras:
                        extras.write({'active': False})
                        _logger.info("  archived duplicates for %s %.1f%%: %s", use, rate, extras.ids)
                else:
                    keep = Tax.create({
                        'name': f"VAT {rate}% ({'Sales' if use == 'sale' else 'Purchase'})",
                        'type_tax_use': use,
                        'amount_type': 'percent',
                        'amount': rate,
                        'company_id': company.id,
                        'tax_group_id': group.id,
                        'active': True,
                        'price_include': False,
                    })
                    _logger.info("  created %s %.1f%% tax id=%s", use, rate, keep.id)

                # ALWAYS normalize repartition lines (fixes the “exactly one base line” error)
                normalize_repartition_lines(keep)
                # Then assign accounts to the tax lines
                set_tax_accounts(keep, acc_collected, acc_paid)
                # Apply FRCS invoice label (A/B/G)
                label = label_map.get(rate)
                if label and keep.invoice_label != label:
                    keep.invoice_label = label

        # Company defaults (pick the 12.5% ones if present, else 0%)
        sale_125 = Tax.search([('company_id', '=', company.id), ('type_tax_use', '=', 'sale'), ('amount', '=', 12.5)], limit=1)
        purch_0 = Tax.search([('company_id', '=', company.id), ('type_tax_use', '=', 'purchase'), ('amount', '=', 0.0)], limit=1)
        vals = {}
        if sale_125:
            vals['account_sale_tax_id'] = sale_125.id
        if purch_0:
            vals['account_purchase_tax_id'] = purch_0.id
        if vals:
            company.write(vals)

    _logger.info("Fiji post-install setup complete.")
