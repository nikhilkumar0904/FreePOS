from odoo import api, models

# All payment methods required by FRCS TaxCore
# Each POS register needs its OWN cash method (Odoo restriction)
# Non-cash methods (card, mobile, wire, check) can be shared across POS configs
PAYMENT_METHODS = [
    # Cash methods - one per POS register
    {
        'name': 'POS Cash',
        'journal_type': 'cash',
        'journal_code': 'POSC',
        'journal_name': 'POS Cash',
        'is_cash_count': True,
        'is_cash': True,
        'pos_name': None,  # links to first POS found
    },
    {
        'name': 'POS Cash 2',
        'journal_type': 'cash',
        'journal_code': 'POSC2',
        'journal_name': 'POS Cash 2',
        'is_cash_count': True,
        'is_cash': True,
        'pos_name': None,  # links to second POS found
    },
    # Special mode methods - Training and Proforma (zero-amount, for TaxCore tagging only)
    {
        'name': 'Training',
        'journal_type': 'bank',
        'journal_code': 'POSTR',
        'journal_name': 'POS Training',
        'is_cash_count': False,
        'is_cash': False,
        'pos_name': None,
    },
    {
        'name': 'Proforma',
        'journal_type': 'bank',
        'journal_code': 'POSPF',
        'journal_name': 'POS Proforma',
        'is_cash_count': False,
        'is_cash': False,
        'pos_name': None,
    },
    # Non-cash methods - shared across all POS configs
    {
        'name': 'POS Card',
        'journal_type': 'bank',
        'journal_code': 'POSB',
        'journal_name': 'POS Card',
        'is_cash_count': False,
        'is_cash': False,
        'pos_name': None,
    },
    {
        'name': 'POS Mobile Money',
        'journal_type': 'bank',
        'journal_code': 'POSM',
        'journal_name': 'POS Mobile Money',
        'is_cash_count': False,
        'is_cash': False,
        'pos_name': None,
    },
    {
        'name': 'POS Wire Transfer',
        'journal_type': 'bank',
        'journal_code': 'POSW',
        'journal_name': 'POS Wire Transfer',
        'is_cash_count': False,
        'is_cash': False,
        'pos_name': None,
    },
    {
        'name': 'POS Check',
        'journal_type': 'bank',
        'journal_code': 'POSCHK',
        'journal_name': 'POS Check',
        'is_cash_count': False,
        'is_cash': False,
        'pos_name': None,
    },
]


class POSJournalSetup(models.TransientModel):
    _name = 'pos.journal.setup'
    _description = 'Auto create or update POS journals and payment methods safely'

    @api.model
    def create_pos_journals(self):
        """Create POS journals and payment methods.
        - Each POS register gets its own cash method
        - Non-cash methods are shared across all POS configs
        """
        company = self.env.company
        Account = self.env['account.account']
        Journal = self.env['account.journal']
        PaymentMethod = self.env['pos.payment.method']
        Config = self.env['pos.config']

        # Find a liquidity account
        acc_domain = [('account_type', '=', 'asset_cash')]
        if 'company_id' in Account._fields:
            acc_domain.append(('company_id', '=', company.id))
        liquidity = Account.search(acc_domain, limit=1)

        all_methods = PaymentMethod.browse()

        for pm_data in PAYMENT_METHODS:
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
            else:
                print(f"[pos_minicoa] Payment method exists: {pm_data['name']}")

            all_methods |= payment_method

        # Get all POS configs without open sessions
        cfg_domain = []
        if 'company_id' in Config._fields:
            cfg_domain.append(('company_id', '=', company.id))
        configs = Config.search(cfg_domain)
        open_configs = configs.filtered(
            lambda c: any(s.state == 'opened' for s in c.session_ids)
        )
        available_configs = configs - open_configs

        if open_configs:
            print(f"[pos_minicoa] Skipping {len(open_configs)} POS config(s) with open sessions.")

        # Separate cash and non-cash methods
        cash_methods = all_methods.filtered(lambda m: m.journal_id.type == 'cash')
        non_cash_methods = all_methods - cash_methods
        cash_list = list(cash_methods)

        # Assign one cash method per POS config, share non-cash across all
        for idx, cfg in enumerate(available_configs):
            cmds = []

            # Assign a unique cash method to each register
            if idx < len(cash_list):
                cash_pm = cash_list[idx]
                if cash_pm not in cfg.payment_method_ids:
                    cmds.append((4, cash_pm.id))

            # Link all non-cash methods
            for pm in non_cash_methods:
                if pm not in cfg.payment_method_ids:
                    cmds.append((4, pm.id))

            if cmds:
                try:
                    cfg.write({'payment_method_ids': cmds})
                    print(f"[pos_minicoa] Linked {len(cmds)} method(s) to POS: {cfg.name}")
                except Exception as e:
                    print(f"[pos_minicoa] Could not link methods to {cfg.name}: {e}")

        return True
