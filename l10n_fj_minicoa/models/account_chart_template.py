# -*- coding: utf-8 -*-
from odoo import api, models
import logging

_logger = logging.getLogger(__name__)

class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @api.model
    def _load(self, template_code=None, company=None, install_demo=False, force_create=True):
        """Fiji localization loader – runs after base chart to ensure control accounts exist."""
        fiji = company if company and company.exists() else self.env.company
        if not (fiji and fiji.country_id and fiji.country_id.code == 'FJ'):
            return super()._load(template_code, company, install_demo, force_create)

        fjd = self.env['res.currency'].search([('name', '=', 'FJD')], limit=1)
        fj_country = self.env.ref('base.fj', raise_if_not_found=False)
        if fjd and fiji.currency_id != fjd:
            fiji.currency_id = fjd.id
            _logger.info("Set company %s currency to FJD", fiji.name)
        # Set fiscal country - critical for tax validation on invoices/bills
        if fj_country and fiji.account_fiscal_country_id != fj_country:
            fiji.account_fiscal_country_id = fj_country.id
            _logger.info("Set company %s fiscal country to Fiji", fiji.name)



        # Run the base loader (creates the full chart of accounts)
        res = super()._load(template_code, company, install_demo, force_create)
        self.env.cr.commit()  # ensure accounts are committed before we look for them

        Account = self.env['account.account'].with_company(fiji)
        Journal = self.env['account.journal'].with_company(fiji)
        Imd = self.env['ir.model.data'].sudo()
        chart_tmpl = self.with_company(fiji)
        PosConfig = self.env['pos.config'].with_company(fiji)

        income_acc = Account.with_company(fiji).search([
            ('code', 'in', ['40000', '40100', '40900']),
        ], limit=1)
        if not income_acc:
            _logger.warning("[Fiji Chart] No income account found! POS accounting may fail.")

        sales_journal = Journal.search([('type', '=', 'sale'), ('company_id', '=', fiji.id)], limit=1)
        if not sales_journal:
            sales_journal = Journal.create({
                'name': 'Point of Sale Sales',
                'type': 'sale',
                'code': 'POSS',
                'company_id': fiji.id,
                'default_account_id': income_acc.id if income_acc else False,
                'currency_id': fiji.currency_id.id,
            })
            _logger.info("[Fiji Chart] Created Sales Journal for POS")

        pos_configs = PosConfig.search([('company_id', '=', fiji.id)])
        for cfg in pos_configs:
            cfg.write({
                'journal_id': sales_journal.id,
                'income_account_id': income_acc.id if income_acc else False,
            })
            _logger.info("[Fiji Chart] Linked journal %s and income account %s to PoS config %s",
                        sales_journal.name, income_acc.display_name if income_acc else "None", cfg.name)


        # ---- Helper functions ----
        def _get_account(account_xmlid, fallback_code):
            """Fetch company account by xmlid first, fallback to plain code search."""
            acc = chart_tmpl.ref(account_xmlid, raise_if_not_found=False) if account_xmlid else None
            if not acc and fallback_code:
                acc = Account.search([('code', '=', fallback_code)], limit=1)
            if not acc:
                _logger.warning("[Fiji Chart] Control account %s/%s not found", account_xmlid, fallback_code)
            return acc

        def _ensure_journal(xmlid, name, jtype, code, account_xmlid, fallback_code):
            """Ensure PoS journal exists with correct control account and FJD currency."""
            account = _get_account(account_xmlid, fallback_code)
            journal = self.env.ref(f'l10n_fj_minicoa.{xmlid}', raise_if_not_found=False)
            if not journal:
                journal = Journal.search([('code', '=', code)], limit=1)

            vals = {
                'name': name,
                'type': jtype,
                'code': code,
                'company_id': fiji.id,
                'default_account_id': account.id if account else False,
                'profit_account_id': account.id if account else False,
                'loss_account_id': account.id if account else False,
                'currency_id': fiji.currency_id.id,  # Force FJD
            }

            if journal:
                journal.write(vals)
            else:
                journal = Journal.create(vals)
                Imd.create({
                    'module': 'l10n_fj_minicoa',
                    'name': xmlid,
                    'model': 'account.journal',
                    'res_id': journal.id,
                    'noupdate': True,
                })

            _logger.info("[Fiji Chart] Journal %s linked to %s", name, account_xmlid or fallback_code)
            return journal

        # Ensure Fiji PoS journals AFTER accounts exist
        cash_journal   = _ensure_journal('fj_pos_cash_journal',   'POS Cash',         'cash', 'CSH1', 'fj_70100', '70100')
        card_journal   = _ensure_journal('fj_pos_card_journal',   'POS Card',         'bank', 'CRD1', 'fj_70200', '70200')
        mobile_journal = _ensure_journal('fj_pos_mobile_journal', 'POS Mobile Money', 'bank', 'MBL1', 'fj_70300', '70300')
        pos_sales_journal = _ensure_journal('fj_pos_sales_journal', 'Point of Sale', 'general', 'POSS', 'income', '40000')


        PosPayment = self.env['pos.payment.method'].with_company(fiji)
        receivable_account = (
            getattr(fiji, 'account_default_pos_receivable_account_id', False)
            or Account.search([
                ('account_type', '=', 'asset_receivable'),
                ('reconcile', '=', True),
            ], limit=1)
        )

        def _ensure_pos_method(label, journal, cash=False):
            if not journal:
                return
            vals = {
                'name': label,
                'company_id': fiji.id,
                'journal_id': journal.id,
                'active': True,
                'is_cash_count': cash,
                'payment_method_type': 'cash' if cash else 'electronic',
            }
            outstanding = receivable_account or journal.default_account_id
            if 'outstanding_account_id' in PosPayment._fields and outstanding:
                vals['outstanding_account_id'] = outstanding.id
            if 'receivable_account_id' in PosPayment._fields and receivable_account:
                vals['receivable_account_id'] = receivable_account.id
            method = PosPayment.with_context(active_test=False).search([
                ('name', '=', label), ('company_id', '=', fiji.id)
            ], limit=1)
            (method.write if method else PosPayment.create)(vals)
        _ensure_pos_method('POS Cash', cash_journal, cash=True)
        _ensure_pos_method('POS Card', card_journal)
        _ensure_pos_method('POS Mobile Money', mobile_journal)




        return res
