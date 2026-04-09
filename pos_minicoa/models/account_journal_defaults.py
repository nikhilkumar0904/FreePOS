from odoo import api, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    @api.model
    def set_default_cash_journal_accounts(self):
        """Assign a liquidity account to cash/bank journals if missing.

        - Prefer the company's first 'asset_cash' account as liquidity.
        - If fields 'default_debit_account_id'/'default_credit_account_id' exist
          (older customizations), write them too to keep views consistent.
        This method is idempotent and safe to call on install/update.
        """
        company = self.env.company
        Account = self.env['account.account'].with_company(company)
        Journal = self.env['account.journal'].with_company(company)

        # Build a robust domain that works across versions (company_id may not exist on account.account)
        acc_domain = [('account_type', '=', 'asset_cash')]
        if 'deprecated' in Account._fields:
            acc_domain.append(('deprecated', '=', False))
        elif 'active' in Account._fields:
            acc_domain.append(('active', '=', True))
        if 'company_id' in Account._fields:
            acc_domain.append(('company_id', '=', company.id))

        liquidity = Account.search(acc_domain, limit=1)

        if not liquidity:
            return True

        # Target cash/bank journals for this company
        j_domain = [('type', 'in', ('cash', 'bank'))]
        if 'company_id' in Journal._fields:
            j_domain.append(('company_id', '=', company.id))
        journals = Journal.search(j_domain)

        # Decide what to write based on available fields in this Odoo
        write_keys = ['default_account_id']
        if 'default_debit_account_id' in self._fields and 'default_credit_account_id' in self._fields:
            write_keys += ['default_debit_account_id', 'default_credit_account_id']

        vals = {key: liquidity.id for key in write_keys}

        # Only write when missing to avoid overriding explicit configs
        for j in journals:
            needs = False
            if not j.default_account_id:
                needs = True
            elif 'default_debit_account_id' in write_keys and not getattr(j, 'default_debit_account_id', False):
                needs = True
            elif 'default_credit_account_id' in write_keys and not getattr(j, 'default_credit_account_id', False):
                needs = True
            if needs:
                try:
                    j.write(vals)
                except Exception:
                    # Never break install/upgrade for minor write issues
                    continue

        return True
