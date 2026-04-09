from odoo import fields, models, _
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template('fj_minicoa')
    def _get_fj_minicoa_template_data(self):
        # Minimal template metadata so it appears in Fiscal Localization.
        # Uses generic_coa as parent so default behaviors apply unless overridden.
        return {
            'name': _('Fiji - MiniCOA'),
            'parent': 'generic_coa',
            'country': 'fj',
            'visible': True,
            'sequence': 100,
            'code_digits': 6,
            # Override default property accounts expected by the chart loader
            # so it doesn't try to resolve generic ids like 'income' -> account.<company>_income
            'property_account_receivable_id': 'receivable',
            'property_account_payable_id': 'payable',
            'property_account_income_categ_id': 'income',
            'property_account_expense_categ_id': 'expense',
        }

    @template('fj_minicoa', 'res.company')
    def _get_fj_minicoa_res_company(self):
        # Apply Fiji country and optional defaults when installing the template.
        return {
            self.env.company.id: {
                'account_fiscal_country_id': 'base.fj',
                # Set a sensible FY if desired; comment out if not needed.
                # 'fiscalyear_last_month': '12',
                # 'fiscalyear_last_day': 31,
                # Link default taxes provided by this template (CSV ids)
                'account_sale_tax_id': 'fj_tax_sale_125',
                'account_purchase_tax_id': 'fj_tax_purchase_125',
                # Default revenue/expense category accounts
                'property_account_income_categ_id': 'income',
                'property_account_expense_categ_id': 'expense',
                # Optionally set default receivable/payable (can be inferred by Odoo)
                'property_account_receivable_id': 'receivable',
                'property_account_payable_id': 'payable',
                # Needed by Point of Sale postings (used for session receivables and payments)
                'account_default_pos_receivable_account_id': 'receivable',
            },
        }
